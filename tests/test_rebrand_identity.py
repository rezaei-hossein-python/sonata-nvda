import runpy
from pathlib import Path


root = Path(__file__).resolve().parents[1]


def test_public_addon_identity_is_distinct():
    addon_info = runpy.run_path(str(root / "buildVars.py"))["addon_info"]
    assert addon_info["addon_name"] == "nvdaPiperDriver"
    assert addon_info["addon_summary"] == "NVDA Piper Driver"
    assert addon_info["addon_version"] == "3.2.0"


def test_proven_internal_runtime_identity_is_preserved():
    driver = (
        root / "addon/synthDrivers/sonata_neural_voices/__init__.py"
    ).read_text(encoding="utf-8")
    assert 'description = "NVDA Piper Driver"' in driver
    assert 'name = "sonata_neural_voices"' in driver
    assert (root / "addon/globalPlugins/sonata_tts_global_plugin").is_dir()
    assert not (root / "addon/synthDrivers/nvdaPiperDriver").exists()
    assert not (root / "addon/globalPlugins/nvdaPiperDriver").exists()


def test_sonata_storage_and_settings_paths_are_preserved():
    constants = (
        root / "addon/synthDrivers/sonata_neural_voices/const.py"
    ).read_text(encoding="utf-8")
    config_source = (
        root / "addon/synthDrivers/sonata_neural_voices/_config.py"
    ).read_text(encoding="utf-8")
    install_tasks = (root / "addon/installTasks.py").read_text(encoding="utf-8")
    assert 'globalVars.appArgs.configPath, "sonata"' in constants
    assert 'SONATA_VOICES_BASE_DIR, "voices", "piper"' in constants
    assert 'config.conf["speech"]["sonata_neural_voices"]' in config_source
    assert '"sonata", "voices", "piper"' in install_tasks


def test_maintainer_and_upstream_attribution_are_both_public():
    readme = (root / "readme.md").read_text(encoding="utf-8")
    release_notes = (root / "docs/releases/3.2.0.md").read_text(encoding="utf-8")
    for text in (readme, release_notes):
        assert "Hosein Rezaii" in text
        assert "rezaii.hosein@gmail.com" in text
        assert "Musharraf Omer" in text
        assert "https://github.com/mush42/sonata-nvda" in text


def test_migration_documentation_preserves_voice_library():
    readme = (root / "readme.md").read_text(encoding="utf-8")
    assert "<NVDA configPath>\\sonata\\voices\\piper" in readme
    assert "Removing the old add-on does not remove installed voices" in readme
    assert "internal synthesizer ID remains `sonata_neural_voices`" in readme


test_public_addon_identity_is_distinct()
test_proven_internal_runtime_identity_is_preserved()
test_sonata_storage_and_settings_paths_are_preserved()
test_maintainer_and_upstream_attribution_are_both_public()
test_migration_documentation_preserves_voice_library()
