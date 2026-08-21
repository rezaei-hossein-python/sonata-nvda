import contextlib
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


root = Path(__file__).resolve().parents[1]


class FakeLog:
    def __init__(self):
        self.records = []

    def _record(self, level, message, *args, **kwargs):
        if args:
            message = message % args
        self.records.append((level, message, kwargs))

    def debug(self, message, *args, **kwargs):
        self._record("debug", message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self._record("info", message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self._record("warning", message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self._record("error", message, *args, **kwargs)


class FakeAddon:
    def __init__(
        self,
        name,
        version,
        *,
        pending=False,
        pending_install=False,
        request_error=None,
    ):
        self.name = name
        self.version = version
        self.isPendingRemove = pending
        self.isPendingInstall = pending_install
        self.request_error = request_error
        self.request_calls = 0

    def requestRemove(self):
        self.request_calls += 1
        if self.request_error is not None:
            raise self.request_error
        self.isPendingRemove = True


def load_install_tasks(config_path):
    logger = FakeLog()
    replacements = {
        "globalVars": types.SimpleNamespace(
            appArgs=types.SimpleNamespace(configPath=str(config_path))
        ),
        "logHandler": types.SimpleNamespace(log=logger),
    }
    previous = {name: sys.modules.get(name) for name in replacements}
    sys.modules.update(replacements)
    try:
        spec = importlib.util.spec_from_file_location(
            "nvdaPiperDriver_installTasks_under_test",
            root / "addon/installTasks.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        for name, old_module in previous.items():
            if old_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module
    return module, logger


@contextlib.contextmanager
def fake_addon_handler(addons=None, error=None):
    def get_available_addons():
        if error is not None:
            raise error
        return iter(addons or ())

    previous = sys.modules.get("addonHandler")
    sys.modules["addonHandler"] = types.SimpleNamespace(
        getAvailableAddons=get_available_addons
    )
    try:
        yield
    finally:
        if previous is None:
            sys.modules.pop("addonHandler", None)
        else:
            sys.modules["addonHandler"] = previous


def tree_hashes(path):
    path = Path(path)
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def write_starter_fixture(payload, keys):
    voices = []
    for index, key in enumerate(keys):
        contents = f"starter-{index}".encode("ascii")
        voice_dir = payload / key
        voice_dir.mkdir(parents=True)
        (voice_dir / "voice.onnx").write_bytes(contents)
        voices.append({
            "key": key,
            "files": [{
                "name": "voice.onnx",
                "size": len(contents),
                "sha256": hashlib.sha256(contents).hexdigest(),
            }],
        })
    manifest = {
        "schema": 1,
        "voices": voices,
    }
    (payload / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class LegacyRemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name)
        self.module, self.log = load_install_tasks(self.config_path)
        self.payload = self.config_path / "starter-payload"
        self.starter_keys = (
            "en_US-ljspeech-medium",
            "fr_FR-mls-medium",
            "de_DE-mls-medium",
            "es_ES-carlfm-x_low",
        )
        write_starter_fixture(self.payload, self.starter_keys)
        self.module.STARTER_PACK_DIRECTORY = self.payload

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sonata_3_1_1_is_detected_and_requested_once(self):
        legacy = FakeAddon("sonata_neural_voices", "3.1.1")
        with fake_addon_handler([legacy]):
            self.assertTrue(self.module._remove_legacy_sonata())
        self.assertEqual(legacy.request_calls, 1)

    def test_other_addon_ids_are_ignored(self):
        other = FakeAddon("unrelatedPiperAddon", "3.1.1")
        with fake_addon_handler([other]):
            self.assertFalse(self.module._remove_legacy_sonata())
        self.assertEqual(other.request_calls, 0)

    def test_other_sonata_versions_are_left_for_manual_review(self):
        addons = [
            FakeAddon("sonata_neural_voices", version)
            for version in ("3.1.0", "3.2.0", "4.0.0")
        ]
        with fake_addon_handler(addons):
            self.assertFalse(self.module._remove_legacy_sonata())
        self.assertEqual([addon.request_calls for addon in addons], [0, 0, 0])
        messages = "\n".join(message for _, message, _ in self.log.records)
        self.assertIn("automatic migration applies only to version 3.1.1", messages)

    def test_installation_succeeds_when_legacy_addon_is_absent(self):
        current_pending = FakeAddon(
            "nvdaPiperDriver", "3.2.1", pending_install=True
        )
        with fake_addon_handler([current_pending]):
            self.module.onInstall()
        voices = self.config_path / "sonata" / "voices" / "piper"
        self.assertEqual(
            sorted(path.name for path in voices.iterdir() if path.is_dir()),
            sorted(self.starter_keys),
        )

    def test_legacy_migration_produces_zero_voice_tree_changes(self):
        voices = self.config_path / "sonata" / "voices" / "piper"
        key = "en_US-existing-medium"
        existing = voices / key
        existing.mkdir(parents=True)
        (existing / "voice.onnx").write_bytes(b"user-model-bytes")
        (existing / "voice.onnx.json").write_bytes(b"user-config-bytes")
        legacy = FakeAddon("sonata_neural_voices", "3.1.1")
        current_pending = FakeAddon(
            "nvdaPiperDriver", "3.2.1", pending_install=True
        )
        before = tree_hashes(voices)
        with fake_addon_handler([legacy, current_pending]):
            self.module.onInstall()
        self.assertEqual(tree_hashes(voices), before)
        self.assertEqual(legacy.request_calls, 1)

    def test_repeated_install_does_not_duplicate_removal_request(self):
        legacy = FakeAddon("sonata_neural_voices", "3.1.1")
        with fake_addon_handler([legacy]):
            self.assertTrue(self.module._remove_legacy_sonata())
            self.assertTrue(self.module._remove_legacy_sonata())
        self.assertEqual(legacy.request_calls, 1)

    def test_existing_nvda_piper_driver_update_is_safe(self):
        current = FakeAddon("nvdaPiperDriver", "3.2.0")
        current_pending = FakeAddon(
            "nvdaPiperDriver", "3.2.1", pending_install=True
        )
        voices = self.config_path / "sonata" / "voices" / "piper"
        voices.mkdir(parents=True)
        (voices / "user-voice.onnx").write_bytes(b"user-data")
        before = tree_hashes(voices)
        with fake_addon_handler([current, current_pending]):
            self.module.onInstall()
        self.assertEqual(tree_hashes(voices), before)
        self.assertEqual(current.request_calls, 0)

    def test_addon_enumeration_failure_is_logged_and_non_fatal(self):
        voices = self.config_path / "sonata" / "voices" / "piper"
        voices.mkdir(parents=True)
        (voices / "user-voice.onnx").write_bytes(b"user-data")
        before = tree_hashes(voices)
        with fake_addon_handler(error=RuntimeError("enumeration failed")):
            self.module.onInstall()
        self.assertEqual(tree_hashes(voices), before)
        self.assertTrue(any(level == "error" for level, _, _ in self.log.records))

    def test_request_remove_failure_is_logged_and_non_fatal(self):
        legacy = FakeAddon(
            "sonata_neural_voices",
            "3.1.1",
            request_error=RuntimeError("state write failed"),
        )
        current_pending = FakeAddon(
            "nvdaPiperDriver", "3.2.1", pending_install=True
        )
        with fake_addon_handler([legacy, current_pending]):
            self.module.onInstall()
        self.assertEqual(legacy.request_calls, 1)
        self.assertTrue(any(level == "error" for level, _, _ in self.log.records))

    def test_repeated_migration_callbacks_never_deploy_starters(self):
        voices = self.config_path / "sonata" / "voices" / "piper"
        voices.mkdir(parents=True)
        (voices / "user-voice.onnx").write_bytes(b"user-data")
        legacy = FakeAddon("sonata_neural_voices", "3.1.1")
        current_pending = FakeAddon(
            "nvdaPiperDriver", "3.2.1", pending_install=True
        )
        before = tree_hashes(voices)
        with fake_addon_handler([legacy, current_pending]):
            self.module.onInstall()
            self.module.onInstall()
        self.assertEqual(tree_hashes(voices), before)
        self.assertEqual(legacy.request_calls, 1)

    def test_other_sonata_version_skips_starters_without_removal(self):
        legacy = FakeAddon("sonata_neural_voices", "3.1.0")
        current_pending = FakeAddon(
            "nvdaPiperDriver", "3.2.1", pending_install=True
        )
        with fake_addon_handler([legacy, current_pending]):
            self.module.onInstall()
        voices = self.config_path / "sonata" / "voices" / "piper"
        self.assertFalse(voices.exists())
        self.assertEqual(legacy.request_calls, 0)

    def test_pending_bundle_alone_is_a_fresh_install(self):
        pending = FakeAddon("nvdaPiperDriver", "3.2.1", pending_install=True)
        self.assertEqual(
            self.module._get_install_mode((pending,)),
            self.module._INSTALL_MODE_FRESH,
        )

    def test_identity_failure_skips_starters(self):
        broken = types.SimpleNamespace(name="nvdaPiperDriver")
        with fake_addon_handler([broken]):
            self.module.onInstall()
        voices = self.config_path / "sonata" / "voices" / "piper"
        self.assertFalse(voices.exists())


suite = unittest.defaultTestLoader.loadTestsFromTestCase(LegacyRemovalTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise AssertionError(
        f"Legacy removal tests failed: failures={len(result.failures)}, "
        f"errors={len(result.errors)}"
    )
