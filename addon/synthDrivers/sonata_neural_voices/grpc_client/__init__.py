# coding: utf-8

import asyncio
import atexit
import os
import subprocess
import time
import sys
from pathlib import Path

import globalVars
from logHandler import log

from ..const import SONATA_VOICES_BASE_DIR
from ..helpers import BIN_DIRECTORY, find_free_port, import_bundled_library


with import_bundled_library():
    import grpc
    from .. import aio
    from .grpc_protos.sonata_grpc_pb2_grpc import sonata_grpcStub
    from .grpc_protos import sonata_grpc_pb2 as msgs


SONATA_GRPC_SERVER_PORT = None
GRPC_SERVER_PROCESS = None
CHANNEL = None
SONATA_GRPC_SERVICE = None


def start_grpc_server():
    """Start or reuse a single persistent sonata-grpc server for this user profile.

    Uses a small PID/port file under SONATA_VOICES_BASE_DIR to avoid launching
    duplicate servers from multiple NVDA processes (NVDA spawns helper processes
    which previously could each start their own server). If an existing server
    is reachable on the recorded port, reuse it instead of starting a new one.
    """
    global GRPC_SERVER_PROCESS, SONATA_GRPC_SERVER_PORT
    # If another module already initialized via globalVars, reuse it
    if hasattr(globalVars, "SONATA_GRPC_SERVER_PORT"):
        SONATA_GRPC_SERVER_PORT = globalVars.SONATA_GRPC_SERVER_PORT
        GRPC_SERVER_PROCESS = globalVars.GRPC_SERVER_PROCESS
        return True

    pidfile = os.path.join(SONATA_VOICES_BASE_DIR, "sonata_grpc.pid")

    # Try to detect an existing server from pidfile and test connectivity
    try:
        if os.path.exists(pidfile):
            with open(pidfile, "r", encoding="utf-8") as f:
                data = f.read().strip().split("\n")
            if len(data) >= 2:
                try:
                    existing_port = int(data[0])
                    existing_pid = int(data[1])
                    # quick connectivity check
                    import socket

                    try:
                        s = socket.create_connection(("127.0.0.1", existing_port), timeout=0.5)
                        s.close()
                        SONATA_GRPC_SERVER_PORT = existing_port
                        # We don't claim ownership of the process handle (it may belong to another NVDA process),
                        # but reusing the existing server avoids duplicates.
                        GRPC_SERVER_PROCESS = None
                        globalVars.SONATA_GRPC_SERVER_PORT = SONATA_GRPC_SERVER_PORT
                        globalVars.GRPC_SERVER_PROCESS = GRPC_SERVER_PROCESS
                        log.info(
                            f"Reusing existing Sonata GRPC server at port {existing_port} (pid {existing_pid})"
                        )
                        return True
                    except Exception:
                        # Not reachable, proceed to start a fresh server
                        pass
                except Exception:
                    pass
    except Exception:
        log.exception("Failed to probe existing sonata_grpc.pid file", exc_info=True)

    SONATA_GRPC_SERVER_PORT = find_free_port()
    grpc_server_exe = os.path.join(BIN_DIRECTORY, "sonata-grpc.exe")
    nvda_espeak_dir = os.path.join(globalVars.appDir, "synthDrivers")
    env = os.environ.copy()
    env.update({
        "SONATA_GRPC_SERVER_PORT": str(SONATA_GRPC_SERVER_PORT),
        "SONATA_ESPEAKNG_DATA_DIRECTORY": os.fspath(nvda_espeak_dir),
        "SONATA_GRPC": "info",
    })
    # Do not detach the process so we can reliably terminate it from this process
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    try:
        server_log_file = os.path.join(SONATA_VOICES_BASE_DIR, "logs", "sonata-grpc.log")
        Path(server_log_file).parent.mkdir(parents=True, exist_ok=True)
        server_stdout = open(server_log_file, "wb")
    except Exception:
        log.exception("Failed to open server log file for writing", exc_info=True)
        server_stdout = subprocess.DEVNULL
    try:
        GRPC_SERVER_PROCESS = subprocess.Popen(
            args=grpc_server_exe,
            cwd=os.fspath(BIN_DIRECTORY),
            env=env,
            creationflags=creationflags,
            stdout=server_stdout,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        log.exception(
            "Failed to start Sonata GRPC server. The synth will not be available.",
            exc_info=True,
        )
        return False

    # Write pidfile so other NVDA processes can detect/reuse this server
    try:
        Path(SONATA_VOICES_BASE_DIR).mkdir(parents=True, exist_ok=True)
        with open(pidfile, "w", encoding="utf-8") as f:
            f.write(f"{SONATA_GRPC_SERVER_PORT}\n{GRPC_SERVER_PROCESS.pid}\n")
    except Exception:
        log.exception("Failed to write sonata_grpc.pid file", exc_info=True)

    globalVars.SONATA_GRPC_SERVER_PORT = SONATA_GRPC_SERVER_PORT
    globalVars.GRPC_SERVER_PROCESS = GRPC_SERVER_PROCESS
    log.info(f"Started Sonata GRPC server, pid {GRPC_SERVER_PROCESS.pid}, port {SONATA_GRPC_SERVER_PORT}")
    return True


@aio.asyncio_coroutine_to_concurrent_future
async def initialize():
    global CHANNEL, SONATA_GRPC_SERVICE, SONATA_GRPC_SERVER_PORT
    start_grpc_server()
    if CHANNEL is not None:
        log.warning("Attempted to re-initialize an already initialized GRPC connection")
        return
    port = SONATA_GRPC_SERVER_PORT
    CHANNEL = grpc.aio.insecure_channel(f"localhost:{port}")
    SONATA_GRPC_SERVICE = sonata_grpcStub(CHANNEL)


@atexit.register
def terminate():
    global CHANNEL, GRPC_SERVER_PROCESS, SONATA_GRPC_SERVER_PORT
    pidfile = os.path.join(SONATA_VOICES_BASE_DIR, "sonata_grpc.pid")
    SONATA_GRPC_SERVER_PORT = None
    aio.terminate()
    if CHANNEL is not None:
        try:
            CHANNEL.close()
        except Exception:
            pass
        CHANNEL = None

    # Prefer terminating the subprocess handle we own
    if GRPC_SERVER_PROCESS is not None:
        try:
            pid = getattr(GRPC_SERVER_PROCESS, "pid", None)
            # Attempt graceful shutdown on Windows first
            try:
                import signal, time
                if sys.platform == "win32" and pid is not None:
                    try:
                        import psutil
                        p = psutil.Process(pid)
                        if p.is_running():
                            try:
                                p.send_signal(signal.CTRL_BREAK_EVENT)
                                p.wait(timeout=2)
                            except Exception:
                                pass
                    except Exception:
                        try:
                            os.kill(pid, signal.CTRL_BREAK_EVENT)
                        except Exception:
                            pass
            except Exception:
                pass

            try:
                GRPC_SERVER_PROCESS.terminate()
            except Exception:
                try:
                    GRPC_SERVER_PROCESS.kill()
                except Exception:
                    log.exception("Failed to terminate Sonata GRPC process via handle", exc_info=True)
        except Exception:
            log.exception("Failed while attempting to stop owned Sonata GRPC process", exc_info=True)
        GRPC_SERVER_PROCESS = None

    # If pidfile exists, and contains a pid, try a best-effort cleanup when it appears to belong to this profile
    try:
        if os.path.exists(pidfile):
            with open(pidfile, "r", encoding="utf-8") as f:
                data = f.read().strip().split("\n")
            if len(data) >= 2:
                try:
                    existing_port = int(data[0])
                    existing_pid = int(data[1])
                    # Attempt to kill only if process still exists and appears to be our server (port check)
                    import socket, signal
                    try:
                        s = socket.socket()
                        s.settimeout(0.5)
                        s.connect(("127.0.0.1", existing_port))
                        s.close()
                        # Process still listening; try to terminate gracefully first
                        try:
                            # Prefer psutil if available for graceful termination
                            import psutil

                            p = psutil.Process(existing_pid)
                            if p.is_running():
                                try:
                                    if sys.platform == "win32":
                                        p.send_signal(signal.CTRL_BREAK_EVENT)
                                        try:
                                            p.wait(timeout=2)
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                try:
                                    p.terminate()
                                    p.wait(timeout=2)
                                except Exception:
                                    try:
                                        p.kill()
                                    except Exception:
                                        pass
                        except Exception:
                            try:
                                os.kill(existing_pid, signal.SIGTERM)
                            except Exception:
                                pass
                    except Exception:
                        # Not listening anymore
                        pass
                except Exception:
                    pass
            try:
                os.remove(pidfile)
            except Exception:
                pass
    except Exception:
        log.exception("Failed during sonata_grpc pidfile cleanup", exc_info=True)


@aio.asyncio_coroutine_to_concurrent_future
async def check_grpc_server(timeout=15) -> str:
    return await asyncio.wait_for(get_sonata_version(), timeout)


async def get_sonata_version():
    resp = await SONATA_GRPC_SERVICE.GetSonataVersion(msgs.Empty())
    return resp.version


@aio.asyncio_coroutine_to_concurrent_future
async def load_voice(config_path):
    """Load a voice, ensuring the config is backend-compatible.
    If the JSON uses single-char->id mappings (phoneme_id_map) or char->list (phoneme_map),
    write a backend-friendly .sonata.json that includes both `phoneme_id_map` (char->list)
    and `phoneme_map` (id->char with numeric-string keys) and pass that path to the server.
    """
    try:
        # Delegate normalization to the permanent normalizer in tts_system.
        from pathlib import Path
        pth = Path(config_path)
        if pth.exists():
            try:
                # Import locally to avoid top-level circular imports.
                from ..tts_system import SonataVoice

                normalized = SonataVoice._normalize_config(None, str(pth))
                if normalized and normalized != str(pth):
                    config_path = str(normalized)
            except Exception:
                # Fall back to passing the original config path if normalization fails
                pass
    except Exception:
        pass
    req = msgs.VoicePath(config_path=config_path)
    return await SONATA_GRPC_SERVICE.LoadVoice(req)


@aio.asyncio_coroutine_to_concurrent_future
async def get_synth_options(voice_id):
    req = msgs.VoiceIdentifier(voice_id=voice_id)
    return await SONATA_GRPC_SERVICE.GetSynthesisOptions(req)


@aio.asyncio_coroutine_to_concurrent_future
async def set_synth_options(
    voice_id, speaker=None, length_scale=None, noise_scale=None, noise_w=None
):
    req = msgs.VoiceSynthesisOptions(
        voice_id=voice_id,
        synthesis_options=msgs.SynthesisOptions(
            speaker=speaker,
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w=noise_w,
        ),
    )
    return await SONATA_GRPC_SERVICE.SetSynthesisOptions(req)


async def speak(
    voice_id, text, rate=None, volume=None, pitch=None, appended_silence_ms=None, streaming=False
):
    speech_args = None
    if any([rate, volume, pitch, appended_silence_ms]):
        speech_args = msgs.SpeechArgs(
            rate=rate,
            volume=volume,
            pitch=pitch,
            appended_silence_ms=appended_silence_ms,
        )
    utterance = msgs.Utterance(
        voice_id=voice_id,
        text=text,
        speech_args=speech_args,
    )
    if streaming:
        stream = SONATA_GRPC_SERVICE.SynthesizeUtteranceRealtime
    else:
        stream = SONATA_GRPC_SERVICE.SynthesizeUtterance
    async for ret in stream(utterance):
        yield ret


async def bench(n=10000):
    initialize()
    t0 = time.perf_counter()
    for i in range(n):
        await get_sonata_version()
    return time.perf_counter() - t0
