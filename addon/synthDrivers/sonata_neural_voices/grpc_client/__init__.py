# coding: utf-8

import asyncio
import atexit
import os
import subprocess
import time
from pathlib import Path

import globalVars
from logHandler import log

from ..const import SONATA_VOICES_BASE_DIR
from ..helpers import BIN_DIRECTORY, find_free_port, import_bundled_library
from .windows_process import KillOnCloseJob


with import_bundled_library():
    import grpc
    from .. import aio
    from .grpc_protos.sonata_grpc_pb2_grpc import sonata_grpcStub
    from .grpc_protos import sonata_grpc_pb2 as msgs


SONATA_GRPC_SERVER_PORT = None
GRPC_SERVER_PROCESS = None
GRPC_SERVER_JOB = None
CHANNEL = None
SONATA_GRPC_SERVICE = None
WINDOWS_GRPC_CREATION_FLAGS = (
    subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
)


def start_grpc_server():
    """Start the profile's Sonata backend without creating a console window."""
    global GRPC_SERVER_JOB, GRPC_SERVER_PROCESS, SONATA_GRPC_SERVER_PORT
    if hasattr(globalVars, "SONATA_GRPC_SERVER_PORT"):
        SONATA_GRPC_SERVER_PORT = globalVars.SONATA_GRPC_SERVER_PORT
        GRPC_SERVER_PROCESS = globalVars.GRPC_SERVER_PROCESS
        return True

    SONATA_GRPC_SERVER_PORT = find_free_port()
    grpc_server_exe = os.path.join(BIN_DIRECTORY, "sonata-grpc.exe")
    nvda_espeak_dir = os.path.join(globalVars.appDir, "synthDrivers")
    env = os.environ.copy()
    env.update({
        "SONATA_GRPC_SERVER_PORT": str(SONATA_GRPC_SERVER_PORT),
        "SONATA_ESPEAKNG_DATA_DIRECTORY": os.fspath(nvda_espeak_dir),
        "SONATA_GRPC": "info",
    })
    # CREATE_NO_WINDOW is intentionally used instead of DETACHED_PROCESS.
    # Windows ignores CREATE_NO_WINDOW when DETACHED_PROCESS is also supplied,
    # while the Popen handle remains sufficient for deterministic termination.
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
            creationflags=WINDOWS_GRPC_CREATION_FLAGS,
            stdout=server_stdout,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        GRPC_SERVER_JOB = KillOnCloseJob()
        GRPC_SERVER_JOB.assign(GRPC_SERVER_PROCESS)
    except Exception:
        log.exception(
            "Failed to start Sonata GRPC server. The synth will not be available.",
            exc_info=True,
        )
        if GRPC_SERVER_PROCESS is not None:
            GRPC_SERVER_PROCESS.terminate()
            GRPC_SERVER_PROCESS.wait(timeout=5)
            GRPC_SERVER_PROCESS = None
        if GRPC_SERVER_JOB is not None:
            GRPC_SERVER_JOB.close()
            GRPC_SERVER_JOB = None
        return False

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
    global CHANNEL, GRPC_SERVER_JOB, GRPC_SERVER_PROCESS, SONATA_GRPC_SERVER_PORT, SONATA_GRPC_SERVICE
    channel = CHANNEL
    process = GRPC_SERVER_PROCESS
    job = GRPC_SERVER_JOB
    CHANNEL = None
    SONATA_GRPC_SERVICE = None
    GRPC_SERVER_PROCESS = None
    GRPC_SERVER_JOB = None
    SONATA_GRPC_SERVER_PORT = None

    if channel is not None and aio.ASYNCIO_EVENT_LOOP is not None:
        try:
            asyncio.run_coroutine_threadsafe(
                channel.close(), aio.ASYNCIO_EVENT_LOOP
            ).result(timeout=5)
        except Exception:
            log.debugWarning("Failed to close Sonata GRPC channel cleanly", exc_info=True)

    if process is not None and process.poll() is None:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            log.warning("Sonata GRPC server did not terminate in time; killing it")
            process.kill()
            process.wait(timeout=5)
        except Exception:
            log.exception("Failed to terminate Sonata GRPC process", exc_info=True)

    if job is not None:
        job.close()

    for attribute in ("SONATA_GRPC_SERVER_PORT", "GRPC_SERVER_PROCESS"):
        if hasattr(globalVars, attribute):
            delattr(globalVars, attribute)
    aio.terminate()


@aio.asyncio_coroutine_to_concurrent_future
async def check_grpc_server(timeout=15) -> str:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("Timed out waiting for Sonata GRPC server")
        try:
            return await asyncio.wait_for(get_sonata_version(), remaining)
        except grpc.aio.AioRpcError as error:
            if error.code() != grpc.StatusCode.UNAVAILABLE:
                raise
            await asyncio.sleep(min(0.1, remaining))


async def get_sonata_version():
    resp = await SONATA_GRPC_SERVICE.GetSonataVersion(msgs.Empty())
    return resp.version


@aio.asyncio_coroutine_to_concurrent_future
async def load_voice(config_path):
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
