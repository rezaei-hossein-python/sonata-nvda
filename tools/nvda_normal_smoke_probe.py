"""Temporary normal-profile smoke probe; copied after package installation only."""

import json
import os

import config
import globalPluginHandler
import globalVars
import speech
import synthDriverHandler
import wx
from logHandler import log


REPORT = os.path.join(globalVars.appArgs.configPath, "sonata-normal-smoke.json")
PREVIEW_URL = (
    "https://rhasspy.github.io/piper-samples/samples/"
    "en/en_US/ljspeech/medium/speaker_0.mp3"
)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report = {}
        wx.CallLater(4000, self._start)

    def _save(self):
        with open(REPORT, "w", encoding="utf-8") as output:
            json.dump(self.report, output, indent=2)

    def _fail(self, stage):
        log.exception(f"Normal Sonata smoke failed at {stage}", exc_info=True)
        self.report["failed_stage"] = stage
        self.report["exception"] = True
        self._restore()

    def _start(self):
        try:
            self.report["initial_synth"] = synthDriverHandler.getSynth().name
            self.report["sonata_available"] = bool(
                synthDriverHandler.setSynth("sonata_neural_voices")
            )
            synth = synthDriverHandler.getSynth()
            self.report["starter_voices_available"] = len(synth.availableVoices) >= 4
            speech.speakMessage("Normal profile Sonata speech is working.")
            self.report["normal_speech"] = True
            from globalPlugins.sonata_tts_global_plugin import voice_manager
            from synthDrivers.sonata_neural_voices import aio, grpc_client
            self.report["voice_manager_available"] = hasattr(
                voice_manager, "SonataVoiceManagerDialog"
            )
            self.process = grpc_client.GRPC_SERVER_PROCESS
            future = aio.THREADED_EXECUTOR.submit(
                voice_manager.play_remote_mp3, PREVIEW_URL
            )
            future.add_done_callback(lambda completed: wx.CallAfter(
                self._preview_done, completed
            ))
        except Exception:
            self._fail("start")

    def _preview_done(self, future):
        try:
            future.result()
            self.report["preview_works"] = True
        except Exception:
            self.report["preview_works"] = False
            log.exception("Normal profile preview failed", exc_info=True)
        self._restore()

    def _restore(self):
        try:
            self.report["restored_espeak"] = bool(
                synthDriverHandler.setSynth("espeak")
            )
            self.report["sonata_grpc_exit"] = (
                not hasattr(self, "process") or self.process.poll() is not None
            )
            config.conf["speech"]["synth"] = "espeak"
            config.conf.save()
        except Exception:
            log.exception("Failed to restore eSpeak after normal smoke", exc_info=True)
            self.report["restored_espeak"] = False
        self.report.setdefault("exception", False)
        self._save()
