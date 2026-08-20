import ast
import gettext
import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]


def test_sonata_voice_api_is_defined_on_class():
    source = root / "addon" / "synthDrivers" / "sonata_neural_voices" / "tts_system.py"
    module = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    voice_class = next(
        node for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "SonataVoice"
    )
    methods = {
        node.name for node in voice_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required = {
        "from_path", "load", "speaker", "noise_scale", "length_scale",
        "noise_w", "is_fast", "variant", "standard_variant_key",
        "fast_variant_key", "synthesize",
    }
    assert required <= methods, f"SonataVoice is missing methods: {sorted(required - methods)}"


def test_runtime_normalization_is_absent():
    driver_dir = root / "addon" / "synthDrivers" / "sonata_neural_voices"
    for relative_path in ("tts_system.py", "grpc_client/__init__.py"):
        source = driver_dir / relative_path
        assert "_normalize_config" not in source.read_text(encoding="utf-8")


def test_driver_lifecycle_is_instance_scoped_and_partial_init_safe():
    source = (
        root / "addon" / "synthDrivers" / "sonata_neural_voices" / "__init__.py"
    ).read_text(encoding="utf-8")
    module_prefix = source[:source.index("class SynthDriver")]
    assert "aio.initialize()" not in module_prefix
    assert "grpc_client.initialize()" not in module_prefix
    assert "grpc_client.terminate()" in source
    assert "super().terminate()" in source
    assert "self._unregisterConfigSaveAction()" in source
    assert 'getattr(self, "_sonata_terminated", False)' in source
    assert 'getattr(self, "_current_task", None)' in source
    assert 'getattr(self, "_player", None)' in source


def test_dependency_free_msgfmt():
    wrapper_path = root / "msgfmt_wrapper.py"
    spec = importlib.util.spec_from_file_location("msgfmt_wrapper", wrapper_path)
    msgfmt_wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(msgfmt_wrapper)

    source = root / "addon" / "locale" / "es" / "LC_MESSAGES" / "nvda.po"
    output = root / ".msgfmt-test.mo"
    try:
        msgfmt_wrapper._write_mo(msgfmt_wrapper._parse_po(source), output)
        with output.open("rb") as mo_file:
            translations = gettext.GNUTranslations(mo_file)
        assert translations.gettext("Cancel") == "Cancelar"
    finally:
        output.unlink(missing_ok=True)


test_sonata_voice_api_is_defined_on_class()
test_runtime_normalization_is_absent()
test_driver_lifecycle_is_instance_scoped_and_partial_init_safe()
test_dependency_free_msgfmt()
