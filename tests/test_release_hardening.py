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
    assert build_vars["addon_name"] == "nvdaPiperDriver"
    assert build_vars["addon_summary"] == "NVDA Piper Driver"
    assert build_vars["addon_version"] == "3.2.0"
    assert "rezaii.hosein@gmail.com" in build_vars["addon_author"]
    assert "Musharraf Omer" in build_vars["addon_author"]
    assert build_vars["addon_publisher"] == (
        "Hosein Rezaii <rezaii.hosein@gmail.com>"
    )
    assert build_vars["addon_updateChannel"] == "stable"
    assert build_vars["addon_license"] == "GPL v2"
    assert build_vars["addon_licenseURL"].startswith("https://")
    assert build_vars["addon_releaseURL"] == (
        "https://github.com/rezaei-hossein-python/sonata-nvda/releases/"
        "download/v3.2.0/nvdaPiperDriver-3.2.0.nvda-addon"
    )


def test_generated_store_metadata_fields():
    metadata = json.loads((root / "3.2.0.json").read_text(encoding="utf-8"))
    required = {
        "addonId", "addonVersionNumber", "addonVersionName", "displayName",
        "publisher", "description", "minNVDAVersion", "lastTestedVersion",
        "channel", "URL", "sha256", "sourceURL", "license", "translations",
    }
    assert required <= metadata.keys()
    assert metadata["addonId"] == "nvdaPiperDriver"
    assert metadata["displayName"] == "NVDA Piper Driver"
    assert metadata["addonVersionName"] == "3.2.0"
    assert metadata["channel"] == "stable"
    assert metadata["URL"].startswith("https://")
    assert metadata["URL"].endswith(".nvda-addon")
    assert metadata["sourceURL"].startswith("https://")
    assert metadata["licenseURL"].startswith("https://")
    assert metadata["translations"] == []


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
    expected_hashes = {
        "en_US-ljspeech-medium": {
            "en_US-ljspeech-medium.onnx": "6f52a751e2349abe7a76735eb09dc1875298c77ea2342ffd2fef79ff81b87f22",
            "en_US-ljspeech-medium.onnx.json": "141d612cc0a95ed7efc1ca936b845c2364967f2e9217c5dbfcf69fc4d6c65860",
            "MODEL_CARD": "fbee1529c89d36b3fe76d7e9f3f832dce17f44900a52d76a9bda735654766b4d",
        },
        "fr_FR-mls-medium": {
            "fr_FR-mls-medium.onnx": "0ed223f78466917f2bae05ee90096ce69ab1fdeb251f55590d0e7422d234e162",
            "fr_FR-mls-medium.onnx.json": "252b0b0a6e4cc4949e23eccb956f9c779986c32f934f2f7e2191e5fdc2edca61",
            "MODEL_CARD": "443ca90f1ed8e57d9fb802da6dc19c302d5d9b51ddbfbf27a17f3fb5c37ad154",
        },
        "de_DE-mls-medium": {
            "de_DE-mls-medium.onnx": "69cd1d2aa5a35839a518966fcc4924b5f93e5f8c948ed0752b1a616ad53f65bf",
            "de_DE-mls-medium.onnx.json": "b0af1c89ddfdc72d32e015729b0e89b99eec13c2c8caa1db7488d98e9e570b40",
            "MODEL_CARD": "ca1bf03a3c287fb6968acfa010e1917f85f0aa59db0f371efc3a2857f4035ffd",
        },
        "es_ES-carlfm-x_low": {
            "es_ES-carlfm-x_low.onnx": "d69677323a907cd4963f42b29c20a98b5d6bfa7f3e64df339915e4650c00d125",
            "es_ES-carlfm-x_low.onnx.json": "d9bdfa9ff01eb2bc9e62e7d2593939d1e4c4d8eb7cf75f972731539d12399966",
            "MODEL_CARD": "a6e62a3d36c37c7702d877f784001208b952e2bf4d17c72a6b5da442fbefb4b3",
        },
    }
    actual_hashes = {
        voice["key"]: {
            file_info["name"]: file_info["sha256"]
            for file_info in voice["files"]
        }
        for voice in manifest["voices"]
    }
    assert actual_hashes == expected_hashes


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


def test_standalone_validator_accepts_real_rt_config_names():
    backend_validation = load_module(
        "standalone_backend_rt_validation",
        root / "tools/standalone_backend_validation.py",
    )
    with tempfile.TemporaryDirectory() as temp:
        voice_dir = Path(temp) / "en_US-lessac+RT-low"
        voice_dir.mkdir()
        config = voice_dir / "en_US-lessac+RT-low.json"
        config.write_text("{}", encoding="utf-8")
        (voice_dir / "encoder.onnx").write_bytes(b"encoder")
        (voice_dir / "decoder.onnx").write_bytes(b"decoder")
        assert backend_validation._find_voice_config(voice_dir) == config


def test_install_tasks_supports_nvda_isolated_addon_namespace():
    source = (root / "addon/installTasks.py").read_text(encoding="utf-8")
    assert "from .starter_voices import" in source
    assert "spec_from_file_location" in source
    assert 'os.path.dirname(__file__), "starter_voices.py"' in source


test_hidden_backend_launch_and_owned_lifecycle()
test_maintainer_and_patch_version_metadata()
test_generated_store_metadata_fields()
test_starter_manifest_and_payload_hashes()
test_starter_install_is_idempotent_and_non_destructive()
test_preview_url_and_failure_handling()
test_standalone_validator_accepts_real_rt_config_names()
test_install_tasks_supports_nvda_isolated_addon_namespace()
