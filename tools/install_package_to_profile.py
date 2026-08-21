"""In-NVDA probe for a real high-level add-on installation or update.

Copy this module into a temporary global-plugin add-on in the target profile and
create ``nvda-piper-install-request.json`` in that profile. Unlike the retired
test helper, this probe never extracts an add-on bundle itself. It calls NVDA
2026.1.1's high-level ``addonStore.install.installAddon`` function, which
performs bundle installation and requests removal of a previous same-ID add-on.

Request format::

    {"package": "C:\\\\path\\\\nvdaPiperDriver-3.2.1.nvda-addon"}

The result is written to ``nvda-piper-install-report.json``. The probe asks NVDA
to restart through ``core.restart()``, validates completed state in the new
process, and then exits through ``core.triggerNVDAExit()``.
"""

import hashlib
import json
import os

import addonHandler
from addonStore.install import installAddon
from addonStore.models.status import AddonStateCategory
import core
import globalPluginHandler
import globalVars
from logHandler import log
import wx


CONFIG_PATH = globalVars.appArgs.configPath
REQUEST_PATH = os.path.join(CONFIG_PATH, "nvda-piper-install-request.json")
REPORT_PATH = os.path.join(CONFIG_PATH, "nvda-piper-install-report.json")
VOICE_PATH = os.path.join(CONFIG_PATH, "sonata", "voices", "piper")


def _file_hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _voice_tree():
    files = {}
    if not os.path.isdir(VOICE_PATH):
        return files
    for parent, _, names in os.walk(VOICE_PATH):
        for name in sorted(names):
            path = os.path.join(parent, name)
            relative = os.path.relpath(path, VOICE_PATH).replace(os.sep, "/")
            files[relative] = _file_hash(path)
    return dict(sorted(files.items()))


def _addons():
    result = []
    for addon in addonHandler.getAvailableAddons():
        result.append({
            "name": addon.name,
            "version": addon.version,
            "path": addon.path,
            "pendingInstall": addon.isPendingInstall,
            "pendingRemove": addon.isPendingRemove,
        })
    return result


def _state(category):
    return sorted(addonHandler.state[category])


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if os.path.isfile(REPORT_PATH):
            try:
                with open(REPORT_PATH, "r", encoding="utf-8") as source:
                    report = json.load(source)
            except Exception:
                report = {}
            if report.get("awaitingRestart"):
                wx.CallLater(3000, self._validate_after_restart)
                return
        wx.CallLater(3000, self._install)

    def _save_and_exit(self, report):
        with open(REPORT_PATH, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
        wx.CallLater(1000, core.triggerNVDAExit)

    def _save_and_restart(self, report):
        with open(REPORT_PATH, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
        wx.CallLater(1000, core.restart)

    def _install(self):
        report = {
            "highLevelInstaller": "addonStore.install.installAddon",
            "voiceTreeBefore": _voice_tree(),
        }
        try:
            with open(REQUEST_PATH, "r", encoding="utf-8") as source:
                request = json.load(source)
            package = os.path.abspath(request["package"])
            report["package"] = package
            report["addonsBefore"] = _addons()
            installAddon(package)
            report["addonsAfter"] = _addons()
            report["pendingInstalls"] = _state(AddonStateCategory.PENDING_INSTALL)
            report["pendingRemovals"] = _state(AddonStateCategory.PENDING_REMOVE)
            report["success"] = True
            report["awaitingRestart"] = True
        except Exception as error:
            log.exception("High-level NVDA add-on installation probe failed")
            report["success"] = False
            report["exceptionType"] = type(error).__name__
            report["exception"] = str(error)
        finally:
            report["voiceTreeAfter"] = _voice_tree()
            report["voiceTreeUnchanged"] = (
                report["voiceTreeBefore"] == report["voiceTreeAfter"]
            )
            if report.get("success"):
                self._save_and_restart(report)
            else:
                self._save_and_exit(report)

    def _validate_after_restart(self):
        try:
            with open(REQUEST_PATH, "r", encoding="utf-8") as source:
                request = json.load(source)
            with open(REPORT_PATH, "r", encoding="utf-8") as source:
                report = json.load(source)
            addons = _addons()
            report["addonsAfterRestart"] = addons
            report["pendingInstallsAfterRestart"] = _state(
                AddonStateCategory.PENDING_INSTALL
            )
            report["pendingRemovalsAfterRestart"] = _state(
                AddonStateCategory.PENDING_REMOVE
            )
            report["voiceTreeAfterRestart"] = _voice_tree()
            report["voiceTreeUnchangedAfterRestart"] = (
                report["voiceTreeBefore"] == report["voiceTreeAfterRestart"]
            )
            expected_id = request.get("expectedId", "nvdaPiperDriver")
            expected_version = request.get("expectedVersion", "3.2.1")
            installed = [
                addon for addon in addons
                if addon["name"] == expected_id and not addon["pendingInstall"]
            ]
            report["loadedManifestVersion"] = (
                installed[0]["version"] if len(installed) == 1 else None
            )
            addons_path = os.path.join(CONFIG_PATH, "addons")
            current_dirs = [
                name for name in os.listdir(addons_path)
                if name.casefold().startswith(expected_id.casefold())
            ]
            report["currentAddonDirectories"] = sorted(current_dirs)
            report["oneInstalledCurrentDirectory"] = current_dirs == [expected_id]
            report["pendingStateClean"] = (
                expected_id.casefold()
                not in {item.casefold() for item in report["pendingInstallsAfterRestart"]}
                and expected_id.casefold()
                not in {item.casefold() for item in report["pendingRemovalsAfterRestart"]}
            )
            report["expectedVersionLoaded"] = (
                report["loadedManifestVersion"] == expected_version
            )
            expected_unchanged = request.get("expectVoiceTreeUnchanged")
            report["voicePolicyMatched"] = (
                expected_unchanged is None
                or report["voiceTreeUnchangedAfterRestart"] == expected_unchanged
            )
            report["completed"] = all((
                report["oneInstalledCurrentDirectory"],
                report["pendingStateClean"],
                report["expectedVersionLoaded"],
                report["voicePolicyMatched"],
            ))
            report["awaitingRestart"] = False
        except Exception as error:
            log.exception("Post-restart NVDA add-on validation failed")
            report = locals().get("report", {})
            report["completed"] = False
            report["postRestartExceptionType"] = type(error).__name__
            report["postRestartException"] = str(error)
        self._save_and_exit(report)
