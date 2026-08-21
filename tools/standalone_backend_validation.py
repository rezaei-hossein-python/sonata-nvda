"""Validate real Piper downloads and sonata-grpc without importing NVDA."""

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRIVER_DIR = ROOT / "addon" / "synthDrivers" / "sonata_neural_voices"
LIB_DIR = DRIVER_DIR / "lib"
VOICE_DOWNLOAD = ROOT / "addon" / "globalPlugins" / "sonata_tts_global_plugin" / "voice_download.py"


@contextlib.contextmanager
def _bundled_library():
    sys.path.insert(0, str(LIB_DIR))
    try:
        yield
    finally:
        sys.path.remove(str(LIB_DIR))


def _load_voice_download(voices_dir):
    """Load upstream voice_download.py with only its NVDA UI imports stubbed."""
    package_name = "standalone_sonata_download"
    package = types.ModuleType(package_name)
    package.__path__ = [str(VOICE_DOWNLOAD.parent)]
    package.SONATA_VOICES_DIR = str(voices_dir)

    class TextToSpeechSystem:
        @staticmethod
        def get_voice_variants(key):
            standard = key.replace("+RT", "")
            language, name, quality = standard.split("-")
            return standard, f"{language}-{name}+RT-{quality}"

        @staticmethod
        def load_piper_voices_from_nvda_config_dir():
            return []

    package.SonataTextToSpeechSystem = TextToSpeechSystem
    helpers = types.ModuleType(f"{package_name}.helpers")
    helpers.import_bundled_library = _bundled_library
    sys.modules[package_name] = package
    sys.modules[helpers.__name__] = helpers

    wx = types.ModuleType("wx")
    wx.YES_NO = wx.ICON_WARNING = wx.ICON_ERROR = wx.YES = 0
    wx.CallAfter = lambda callback, *args, **kwargs: callback(*args, **kwargs)
    core = types.ModuleType("core")
    core.restart = lambda: None
    gui = types.ModuleType("gui")
    gui.mainFrame = None
    gui.messageBox = lambda *args, **kwargs: 0
    language_handler = types.ModuleType("languageHandler")
    language_handler.normalizeLanguage = lambda language: language.replace("-", "_")
    log_handler = types.ModuleType("logHandler")
    log_handler.log = types.SimpleNamespace(
        error=lambda *args, **kwargs: None,
        exception=lambda *args, **kwargs: None,
    )
    stubs = {
        "wx": wx,
        "core": core,
        "gui": gui,
        "languageHandler": language_handler,
        "logHandler": log_handler,
    }
    previous = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location(
            f"{package_name}.voice_download", VOICE_DOWNLOAD
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _file_md5(path):
    digest = hashlib.md5()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_and_install(module, voice, download_dir, voices_dir):
    target_dir = voices_dir / voice.key
    target_dir.mkdir(parents=True)
    files = []
    for voice_file in voice.files:
        result_file, downloaded, digest = module.PiperVoiceDownloader._do_download_file(
            voice_file, str(download_dir), lambda _progress: None
        )
        downloaded = Path(downloaded)
        size_ok = downloaded.stat().st_size == result_file.size_in_bytes
        hash_ok = digest == result_file.md5hash == _file_md5(downloaded)
        if not size_ok or not hash_ok:
            raise RuntimeError(
                f"catalog validation failed for {result_file.name}: "
                f"size_ok={size_ok}, hash_ok={hash_ok}"
            )
        shutil.copy2(downloaded, target_dir / result_file.name)
        files.append({
            "name": result_file.name,
            "size": downloaded.stat().st_size,
            "md5": digest,
        })
    return files


def _wait_for_backend(stub_class, messages, port, process):
    import grpc

    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    stub = stub_class(channel)
    for _attempt in range(120):
        if process.poll() is not None:
            raise RuntimeError(f"sonata-grpc exited early with code {process.returncode}")
        try:
            version = stub.GetSonataVersion(messages.Empty(), timeout=1).version
            return channel, stub, version
        except grpc.RpcError:
            time.sleep(0.25)
    raise RuntimeError("sonata-grpc did not become ready")


def _find_voice_config(voice_dir):
    configs = list(voice_dir.glob("*.onnx.json"))
    if not configs:
        # Sonata RT archives contain encoder.onnx, decoder.onnx and a plain
        # <voice>+RT-<quality>.json configuration file.
        configs = list(voice_dir.glob("*.json"))
    if len(configs) != 1:
        raise RuntimeError(
            f"expected exactly one voice config in {voice_dir}, found {configs}"
        )
    return configs[0]


def _synthesize(stub, messages, voice_dir, text):
    config = _find_voice_config(voice_dir)
    voice_info = stub.LoadVoice(
        messages.VoicePath(config_path=str(config.resolve())), timeout=30
    )
    total = 0
    utterance = messages.Utterance(voice_id=voice_info.voice_id, text=text)
    for result in stub.SynthesizeUtterance(utterance, timeout=120):
        samples = result.wav_samples
        chunk = samples.wav_samples if hasattr(samples, "wav_samples") else samples
        total += len(chunk)
    if total <= 0:
        raise RuntimeError(f"no PCM returned for {voice_dir.name}")
    return {"voice_id": voice_info.voice_id, "pcm_bytes": total}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--espeak-dir", required=True, type=Path)
    parser.add_argument(
        "--voices", nargs="+", default=["en_GB-alan-medium", "fr_FR-gilles-low"]
    )
    parser.add_argument("--rt-voice")
    parser.add_argument("--rt-only", action="store_true")
    parser.add_argument(
        "--installed-only", action="store_true",
        help="Skip network access and synthesize voices already in the work directory",
    )
    args = parser.parse_args()
    work_dir = args.work_dir.resolve()
    downloads = work_dir / "downloads"
    voices_base = work_dir / "sonata"
    voices_dir = voices_base / "voices" / "piper"
    downloads.mkdir(parents=True, exist_ok=True)
    voices_dir.mkdir(parents=True, exist_ok=True)
    if not (args.espeak_dir / "espeak-ng-data").is_dir():
        raise SystemExit(f"missing eSpeak data below {args.espeak_dir}")

    if args.installed_only:
        selected = [types.SimpleNamespace(key=key) for key in args.voices]
        for voice in selected:
            if not (voices_dir / voice.key).is_dir():
                raise RuntimeError(f"installed voice missing: {voice.key}")
        report = {
            "catalog_count": None,
            "catalog_load": "skipped-offline",
            "voices": {voice.key: {"installed": True} for voice in selected},
        }
    else:
        voice_download = _load_voice_download(voices_dir)
        catalog = voice_download.get_available_voices(force_online=not args.rt_only)
        catalog_by_key = {voice.key: voice for voice in catalog}
        selected = []
        for key in args.voices:
            voice = catalog_by_key.get(key)
            if voice is None:
                raise RuntimeError(f"voice missing from catalog: {key}")
            selected.append(voice)
        report = {
            "catalog_count": len(catalog),
            "catalog_language_count": len({voice.language.code for voice in catalog}),
            "catalog_load": True,
            "voices": {},
        }
    if args.rt_voice and not args.installed_only:
        rt_voice = catalog_by_key.get(args.rt_voice)
        if rt_voice is None or not rt_voice.has_rt_variant:
            raise RuntimeError(f"RT variant unavailable for {args.rt_voice}")
        archive_name = rt_voice.get_rt_variant_download_url().rsplit("/", 1)[-1]
        archive = voice_download.PiperRTVoiceDownloader._do_download_archive(
            rt_voice.get_rt_variant_download_url(), archive_name, str(downloads),
            lambda _progress: None,
        )
        rt_key = voice_download.install_voice_from_tar_archive(archive, voices_dir)
        report["rt_variant"] = {
            "base_voice": args.rt_voice,
            "installed_key": rt_key,
            "archive": archive_name,
            "archive_size": Path(archive).stat().st_size,
        }
        if args.rt_only:
            report_path = work_dir / "rt-variant-report.json"
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            return
    if not args.installed_only:
        for voice in selected:
            report["voices"][voice.key] = {
                "files": _download_and_install(
                    voice_download, voice, downloads, voices_dir
                ),
                "installed": True,
            }

    sys.path.insert(0, str(LIB_DIR))
    sys.path.insert(0, str(DRIVER_DIR / "grpc_client"))
    import grpc_protos.sonata_grpc_pb2 as messages
    from grpc_protos.sonata_grpc_pb2_grpc import sonata_grpcStub

    port = _free_port()
    environment = os.environ.copy()
    environment["SONATA_VOICES_BASE_DIR"] = str(voices_base)
    environment["SONATA_ESPEAKNG_DATA_DIRECTORY"] = str(args.espeak_dir.resolve())
    environment["SONATA_GRPC_SERVER_PORT"] = str(port)
    environment["SONATA_GRPC"] = "info"
    log_path = work_dir / "sonata-grpc.log"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [str(DRIVER_DIR / "bin" / "sonata-grpc.exe")],
            cwd=DRIVER_DIR / "bin",
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            ),
        )
        channel = None
        try:
            channel, stub, version = _wait_for_backend(
                sonata_grpcStub, messages, port, process
            )
            report["backend_version"] = version
            order = selected + selected[:1]
            sample_text = {
                "en": "Hello from Sonata.",
                "fr": "Bonjour depuis Sonata.",
                "de": "Hallo von Sonata.",
                "es": "Hola desde Sonata.",
            }
            for index, voice in enumerate(order, 1):
                result = _synthesize(
                    stub, messages, voices_dir / voice.key,
                    sample_text.get(voice.key[:2], "Testing Sonata."),
                )
                report["voices"][voice.key].setdefault("synthesis", []).append(result)
                report[f"switch_{index}"] = voice.key
        finally:
            if channel is not None:
                channel.close()
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            report["backend_exit_code"] = process.returncode

    report_path = work_dir / "standalone-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
