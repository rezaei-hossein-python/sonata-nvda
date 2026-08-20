"""Install the built package into an explicitly supplied NVDA profile."""

import argparse
import importlib.util
import os
import shutil
import sys
import tempfile
import types
import zipfile
from pathlib import Path


class Logger:
    def info(self, message):
        print(message)

    def debug(self, message):
        print(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("profile", type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    profile = args.profile.resolve()
    addons = profile / "addons"
    target = addons / "sonata_neural_voices"
    if target.exists():
        raise SystemExit(f"Refusing to overwrite existing add-on directory: {target}")
    addons.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".sonata-install-", dir=addons))
    try:
        with zipfile.ZipFile(package) as archive:
            archive.extractall(temp)
        manifest = (temp / "manifest.ini").read_text(encoding="utf-8-sig")
        if "name = sonata_neural_voices" not in manifest or "version = 3.1.1" not in manifest:
            raise RuntimeError("Unexpected Sonata package manifest")
        os.rename(temp, target)
        temp = None
    finally:
        if temp is not None:
            shutil.rmtree(temp, ignore_errors=True)

    global_vars = types.ModuleType("globalVars")
    global_vars.appArgs = types.SimpleNamespace(configPath=str(profile))
    log_handler = types.ModuleType("logHandler")
    log_handler.log = Logger()
    sys.modules["globalVars"] = global_vars
    sys.modules["logHandler"] = log_handler
    sys.path.insert(0, str(target))
    try:
        spec = importlib.util.spec_from_file_location(
            "normal_profile_install_tasks", target / "installTasks.py"
        )
        install_tasks = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(install_tasks)
        install_tasks.onInstall()
    finally:
        sys.path.remove(str(target))
    print(f"Installed Sonata 3.1.1 from {package} into {profile}")


if __name__ == "__main__":
    main()
