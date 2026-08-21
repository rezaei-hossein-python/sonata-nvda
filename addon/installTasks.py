# coding: utf-8

# Copyright (c) 2023 Musharraf Omer
# This file is covered by the GNU General Public License.


import contextlib
import importlib.util
import os
import shutil
import sys
import tempfile

import globalVars
from logHandler import log

try:
    # NVDA 2026 imports install tasks inside the isolated addons.<id> package.
    from .starter_voices import STARTER_PACK_DIRECTORY, install_starter_voices
except ImportError:
    # NVDA's synthetic add-on namespace has no searchable package path. Load
    # this verified sibling explicitly; the module uses only the standard library.
    _starter_path = os.path.join(os.path.dirname(__file__), "starter_voices.py")
    _starter_spec = importlib.util.spec_from_file_location(
        f"{__name__}._starter_voices", _starter_path
    )
    _starter_module = importlib.util.module_from_spec(_starter_spec)
    _starter_spec.loader.exec_module(_starter_module)
    STARTER_PACK_DIRECTORY = _starter_module.STARTER_PACK_DIRECTORY
    install_starter_voices = _starter_module.install_starter_voices
    del _starter_module, _starter_path, _starter_spec


_DIR = os.path.abspath(os.path.dirname(__file__))
_PIPER_SYNTH_DIR = os.path.join(_DIR, "synthDrivers", "sonata_neural_voices")
LIB_DIR = os.path.join(_PIPER_SYNTH_DIR, "lib")
BIN_DIR = os.path.join(_PIPER_SYNTH_DIR, "bin")
del _DIR, _PIPER_SYNTH_DIR

_LEGACY_ADDON_ID = "sonata_neural_voices"
_LEGACY_ADDON_VERSION = "3.1.1"


def onUninstall():
    with _temporary_import_psutil() as psutil:
        force_kill_sonata_grpc_server(psutil)


def onInstall():
    voices_dir = os.path.join(
        globalVars.appArgs.configPath, "sonata", "voices", "piper"
    )
    install_starter_voices(STARTER_PACK_DIRECTORY, voices_dir, logger=log)
    _remove_legacy_sonata()


def _remove_legacy_sonata():
    """Schedule Sonata Neural Voices 3.1.1 for removal on NVDA restart."""
    import addonHandler

    for addon in addonHandler.getAvailableAddons():
        if addon.name != _LEGACY_ADDON_ID or addon.version != _LEGACY_ADDON_VERSION:
            continue
        log.info(
            "Scheduling legacy Sonata Neural Voices 3.1.1 for removal; "
            "the shared Sonata voice directory is preserved"
        )
        addon.requestRemove()
        return True
    return False


def force_kill_sonata_grpc_server(psutil):
    log.debug("Trying to force kill GRPC server process")
    grpc_server_processes = list(filter(
        lambda p: "sonata-grpc" in p.name().lower(),
        psutil.process_iter(attrs=["name", "exe"])
    ))
    grpc_server_exe = os.path.join(BIN_DIR, "sonata-grpc.exe")
    for proc in grpc_server_processes:
        if os.path.samefile(proc.exe(), grpc_server_exe):
            proc.kill()
            log.debug(f"Killed process with pid {proc.pid}")
    psutil.wait_procs(
        grpc_server_processes,
        timeout=5,
    )


@contextlib.contextmanager
def _temporary_import_psutil():
    temp_import_dir = tempfile.TemporaryDirectory()
    src = os.path.join(LIB_DIR, "psutil")
    # py3_lib_src = os.path.join(LIB_DIR, "python3.dll")
    dst = os.path.join(temp_import_dir.name, "psutil")
    shutil.copytree(src, dst)
    # shutil.copy2(py3_lib_src, dst)
    sys.path.insert(0, temp_import_dir.name)
    import psutil
    yield psutil
    sys.path.remove(temp_import_dir.name)
    with contextlib.suppress(Exception):
        temp_import_dir.cleanup()
