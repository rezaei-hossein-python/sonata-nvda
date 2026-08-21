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
_CURRENT_ADDON_ID = "nvdaPiperDriver"

_INSTALL_MODE_FRESH = "fresh"
_INSTALL_MODE_LEGACY_MIGRATION = "legacy-migration"
_INSTALL_MODE_SAME_ID_UPDATE = "same-id-update"
_INSTALL_MODE_UNKNOWN = "unknown"


def onUninstall():
    with _temporary_import_psutil() as psutil:
        force_kill_sonata_grpc_server(psutil)


def onInstall():
    addons = _get_available_addons()
    install_mode = _get_install_mode(addons)
    voices_dir = os.path.join(
        globalVars.appArgs.configPath, "sonata", "voices", "piper"
    )
    if install_mode == _INSTALL_MODE_FRESH:
        install_starter_voices(STARTER_PACK_DIRECTORY, voices_dir, logger=log)
    else:
        log.info(
            "Skipping bundled starter voice deployment during %s installation; "
            "the shared Sonata voice directory will not be modified",
            install_mode,
        )
    _remove_legacy_sonata(addons)


def _get_available_addons():
    """Return one stable NVDA add-on snapshot, or ``None`` on inspection failure.

    Failing closed is intentional: if NVDA's installed state cannot be read, the
    installer continues but does not deploy voices because it cannot prove that
    this is a genuinely fresh installation.
    """
    try:
        import addonHandler

        return tuple(addonHandler.getAvailableAddons())
    except Exception:
        log.error(
            "Unable to inspect installed add-ons; NVDA Piper Driver installation "
            "will continue without deploying starter voices or changing another "
            "add-on's state",
            exc_info=True,
        )
        return None


def _get_install_mode(addons):
    """Classify installation without treating this pending bundle as installed.

    NVDA adds the newly extracted ``nvdaPiperDriver.pendingInstall`` object to
    ``getAvailableAddons()`` before invoking this module.  That one object is
    ignored.  Any already-installed Sonata ID makes this a migration, and any
    already-installed NVDA Piper Driver ID makes this a same-ID update.
    """
    if addons is None:
        return _INSTALL_MODE_UNKNOWN

    legacy_installed = False
    current_installed = False
    for addon in addons:
        try:
            addon_name = addon.name
            is_pending_install = addon.isPendingInstall
        except Exception:
            log.warning(
                "Unable to read an add-on identity while determining installation "
                "mode; starter voice deployment will be skipped",
                exc_info=True,
            )
            return _INSTALL_MODE_UNKNOWN
        if addon_name == _LEGACY_ADDON_ID:
            legacy_installed = True
        elif addon_name == _CURRENT_ADDON_ID and not is_pending_install:
            current_installed = True

    if legacy_installed:
        return _INSTALL_MODE_LEGACY_MIGRATION
    if current_installed:
        return _INSTALL_MODE_SAME_ID_UPDATE
    return _INSTALL_MODE_FRESH


def _remove_legacy_sonata(addons=None):
    """Schedule only Sonata Neural Voices 3.1.1 for removal on NVDA restart.

    Other Sonata versions are deliberately left installed for manual review.
    Removal is requested through NVDA's add-on lifecycle and never touches the
    shared Sonata voice directory.
    """
    if addons is None:
        addons = _get_available_addons()
    if addons is None:
        return False

    for addon in addons:
        try:
            addon_name = addon.name
            addon_version = addon.version
        except Exception:
            log.warning(
                "Ignoring an add-on whose identity could not be read during "
                "legacy Sonata migration",
                exc_info=True,
            )
            continue
        if addon_name != _LEGACY_ADDON_ID:
            continue
        if addon_version != _LEGACY_ADDON_VERSION:
            log.info(
                "Leaving Sonata Neural Voices version %s installed; automatic "
                "migration applies only to version %s",
                addon_version,
                _LEGACY_ADDON_VERSION,
            )
            continue
        try:
            is_pending_remove = addon.isPendingRemove
        except Exception:
            log.warning(
                "Unable to read Sonata Neural Voices pending-removal state; "
                "requesting removal through NVDA's idempotent add-on lifecycle",
                exc_info=True,
            )
            is_pending_remove = False
        if is_pending_remove:
            log.info("Legacy Sonata Neural Voices 3.1.1 is already pending removal")
            return True
        log.info(
            "Scheduling legacy Sonata Neural Voices 3.1.1 for removal; "
            "the shared Sonata voice directory is preserved"
        )
        try:
            addon.requestRemove()
        except Exception:
            log.error(
                "Unable to schedule Sonata Neural Voices 3.1.1 for removal; "
                "NVDA Piper Driver installation will continue and the legacy "
                "add-on can be removed manually",
                exc_info=True,
            )
            return False
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
