# coding: utf-8

# Copyright (c) 2023 Musharraf Omer
# This file is covered by the GNU General Public License.

import wx

import core
import gui
import globalPluginHandler
from logHandler import log

import addonHandler

addonHandler.initTranslation()


from synthDrivers.sonata_neural_voices import aio, helpers
from synthDrivers.sonata_neural_voices.tts_system import (
    SONATA_VOICES_DIR,
    SonataTextToSpeechSystem,
)

from .voice_manager import SonataVoiceManagerDialog


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__voice_manager_shown = False
        self._voice_checker = lambda: wx.CallLater(3000, self._perform_voice_check)
        core.postNvdaStartup.register(self._voice_checker)
        self.itemHandle = gui.mainFrame.sysTrayIcon.menu.Insert(
            4,
            wx.ID_ANY,
            # Translators: label of a menu item
            _("Sonata &voice manager..."),
            # Translators: Sonata's voice manager menu item help
            _("Open the voice manager to preview, install or download sonata voices"),
        )
        gui.mainFrame.sysTrayIcon.menu.Bind(wx.EVT_MENU, self.on_manager, self.itemHandle)

    def on_manager(self, event):
        manager_dialog = SonataVoiceManagerDialog()
        gui.runScriptModalDialog(manager_dialog)
        self.__voice_manager_shown = True

    def _perform_voice_check(self):
        if self.__voice_manager_shown:
            return
        if not any(SonataTextToSpeechSystem.load_piper_voices_from_nvda_config_dir()):
            retval = gui.messageBox(
                # Translators: message telling the user that no voice is installed
                _(
                    "No Sonata voice was found.\n"
                    "You can preview and download voices from the voice manager.\n"
                    "Do you want to open the voice manager now?"
                ),
                # Translators: title of a message telling the user that no Sonata voice was found
                _("Sonata Neural Voices"),
                wx.YES_NO | wx.ICON_WARNING,
            )
            if retval == wx.YES:
                self.on_manager(None)

    def terminate(self):
        try:
            gui.mainFrame.sysTrayIcon.menu.DestroyItem(self.itemHandle)
        except:
            pass
