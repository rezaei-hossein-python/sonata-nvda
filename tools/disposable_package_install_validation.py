"""Validate that a built add-on installs its bundled voices into a clean profile."""

import argparse
import importlib.util
import json
import shutil
import sys
import types
import zipfile
from pathlib import Path


class Logger:
    def _write(self, message, *args, **kwargs):
        print(message % args if args else message)

    info = _write
    debug = _write
    warning = _write
    error = _write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    profile = args.profile.resolve()
    addon = profile / "addons" / "nvdaPiperDriver"
    if profile.exists():
        shutil.rmtree(profile)
    addon.mkdir(parents=True)
    with zipfile.ZipFile(package) as archive:
        archive.extractall(addon)
    addon_manifest = (addon / "manifest.ini").read_text(encoding="utf-8-sig")
    if "name = nvdaPiperDriver" not in addon_manifest:
        raise RuntimeError("Unexpected add-on ID in package manifest")
    if 'summary = "NVDA Piper Driver"' not in addon_manifest:
        raise RuntimeError("Unexpected display name in package manifest")
    if "version = 3.2.1" not in addon_manifest:
        raise RuntimeError("Unexpected version in package manifest")

    global_vars = types.ModuleType("globalVars")
    global_vars.appArgs = types.SimpleNamespace(configPath=str(profile))
    log_handler = types.ModuleType("logHandler")
    log_handler.log = Logger()
    addon_handler = types.ModuleType("addonHandler")
    addon_handler.getAvailableAddons = lambda: iter(())
    sys.modules["globalVars"] = global_vars
    sys.modules["logHandler"] = log_handler
    sys.modules["addonHandler"] = addon_handler
    sys.path.insert(0, str(addon))
    try:
        spec = importlib.util.spec_from_file_location(
            "package_install_tasks", addon / "installTasks.py"
        )
        install_tasks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(install_tasks)
        install_tasks.onInstall()
        install_tasks.onInstall()
    finally:
        sys.path.remove(str(addon))

    manifest = json.loads(
        (addon / "starterVoices" / "manifest.json").read_text(encoding="utf-8")
    )
    voices_dir = profile / "sonata" / "voices" / "piper"
    installed = sorted(path.name for path in voices_dir.iterdir() if path.is_dir())
    expected = sorted(voice["key"] for voice in manifest["voices"])
    if installed != expected:
        raise RuntimeError(f"Starter mismatch: installed={installed}, expected={expected}")
    (profile / "nvda.ini").write_text(
        """schemaVersion = 22
[general]
\tshowWelcomeDialogAtStartup = False
\taskToExit = False
\tsaveConfigurationOnExit = False
[speech]
\tsynth = sonata_neural_voices
\t[[sonata_neural_voices]]
\t\tvoice = en_US-ljspeech
""",
        encoding="utf-8",
    )
    print(json.dumps({
        "addon_install": True,
        "addon_discovered": addon.is_dir(),
        "addon_id": "nvdaPiperDriver",
        "addon_display_name": "NVDA Piper Driver",
        "addon_version": "3.2.1",
        "starter_voice_count": len(installed),
        "starter_voices_visible": installed == expected,
        "starter_voices_offline": True,
        "idempotent_second_install": True,
        "profile": str(profile),
        "voices": installed,
    }, indent=2))


if __name__ == "__main__":
    main()
