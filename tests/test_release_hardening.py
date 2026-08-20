import ast
import hashlib
import importlib.util
import json
import runpy
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hidden_backend_launch_and_owned_lifecycle():
    path = root / "addon/synthDrivers/sonata_neural_voices/grpc_client/__init__.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "subprocess.CREATE_NO_WINDOW" in source
    assert "subprocess.CREATE_NEW_PROCESS_GROUP" in source
    assert "subprocess.DETACHED_PROCESS" not in source
    popen = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Popen"
    )
    keywords = {keyword.arg: keyword.value for keyword in popen.keywords}
    assert isinstance(keywords["creationflags"], ast.Name)
    assert keywords["creationflags"].id == "WINDOWS_GRPC_CREATION_FLAGS"
    assert isinstance(keywords["close_fds"], ast.Constant)
    assert keywords["close_fds"].value is True
    assert "process.terminate()" in source
    assert "process.wait(timeout=5)" in source
    assert "process.kill()" in source
    assert "sonata_grpc.pid" not in source
    assert "KillOnCloseJob" in source
    assert "GRPC_SERVER_JOB.assign(GRPC_SERVER_PROCESS)" in source

    windows_process = load_module(
        "sonata_windows_process",
        path.with_name("windows_process.py"),
    )
    job = windows_process.KillOnCloseJob()
    assert job.handle
    job.close()
    assert job.handle is None


def test_maintainer_and_patch_version_metadata():
    build_vars = runpy.run_path(str(root / "buildVars.py"))["addon_info"]
    assert build_vars["addon_version"] == "3.1.1"
    assert "rezaii.hosein@gmail.com" in build_vars["addon_author"]
    assert "Musharraf Omer" in build_vars["addon_author"]
    assert build_vars["addon_publisher"] == (
        "Hosein Rezaii <rezaii.hosein@gmail.com>"
    )


def test_starter_manifest_and_payload_hashes():
    starter = load_module("starter_voices_payload", root / "addon/starter_voices.py")
    manifest = starter.verify_payload(root / "addon/starterVoices")
    assert len(manifest["voices"]) == 4
    assert {voice["key"][:2] for voice in manifest["voices"]} == {
        "en", "fr", "de", "es"
    }
    assert all(voice["trained_from_scratch"] for voice in manifest["voices"])
    assert all(voice["license"] in {"Public domain", "CC BY 4.0"}
               for voice in manifest["voices"])
    assert all(any(file_info["name"] == "MODEL_CARD" for file_info in voice["files"])
               for voice in manifest["voices"])


def write_fixture_manifest(payload, key, contents):
    voice_dir = payload / key
    voice_dir.mkdir(parents=True)
    (voice_dir / "voice.onnx").write_bytes(contents)
    manifest = {
        "schema": 1,
        "voices": [{
            "key": key,
            "files": [{
                "name": "voice.onnx",
                "size": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
            }],
        }],
    }
    (payload / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_starter_install_is_idempotent_and_non_destructive():
    starter = load_module("starter_voices_install", root / "addon/starter_voices.py")
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        payload = temp / "payload"
        voices = temp / "voices"
        key = "en_US-test-low"
        write_fixture_manifest(payload, key, b"bundled")
        existing = voices / key
        existing.mkdir(parents=True)
        (existing / "voice.onnx").write_bytes(b"user-data")
        result = starter.install_starter_voices(payload, voices)
        assert result[key] == "skipped-existing"
        assert (existing / "voice.onnx").read_bytes() == b"user-data"

        second_key = "fr_FR-test-low"
        payload2 = temp / "payload2"
        write_fixture_manifest(payload2, second_key, b"starter")
        first = starter.install_starter_voices(payload2, voices)
        second = starter.install_starter_voices(payload2, voices)
        assert first[second_key] == "installed"
        assert second[second_key] == "skipped-existing"
        assert (voices / second_key / "voice.onnx").read_bytes() == b"starter"


def test_preview_url_and_failure_handling():
    backend_validation = load_module(
        "standalone_backend_validation",
        root / "tools/standalone_backend_validation.py",
    )

    with tempfile.TemporaryDirectory() as temp:
        module = backend_validation._load_voice_download(Path(temp))
        language = module.PiperVoiceLanguage(
            code="fr_FR", family="fr", region="FR", name_native="français",
            name_english="French", country_english="France",
        )
        voice = module.PiperVoice(
            key="fr_FR-siwis-low", name="siwis",
            quality=module.PiperVoiceQualityLevel.Low,
            num_speakers=1, speaker_id_map={}, language=language, files=[],
        )
        assert voice.get_preview_url() == (
            "https://rhasspy.github.io/piper-samples/samples/"
            "fr/fr_FR/siwis/low/speaker_0.mp3"
        )

    path = root / "addon/globalPlugins/sonata_tts_global_plugin/voice_manager.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    callback = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_on_preview_complete"
    )
    callback_source = ast.get_source_segment(source, callback)
    assert "future.result()" in callback_source
    assert "gui.messageBox" in callback_source
    assert "log.exception" in callback_source
    assert "self.voices_list.SetFocus()" in callback_source
    player = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "play_remote_mp3"
    )
    player_source = ast.get_source_segment(source, player)
    assert "max_redirects=10" in player_source
    assert "resp.raise_for_status()" in player_source
    assert "wave.open" in player_source
    assert "decoded_file.samples.tobytes()" in player_source
    assert "miniaudio.wav_write_file" not in player_source
    assert "winsound.SND_PURGE" not in player_source
    assert "winsound.SND_FILENAME" in player_source


test_hidden_backend_launch_and_owned_lifecycle()
test_maintainer_and_patch_version_metadata()
test_starter_manifest_and_payload_hashes()
test_starter_install_is_idempotent_and_non_destructive()
test_preview_url_and_failure_handling()
