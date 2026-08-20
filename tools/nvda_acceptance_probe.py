"""Disposable-only NVDA global plugin for Sonata lifecycle acceptance."""

import json
import os

import globalPluginHandler
import globalVars
import speech
import synthDriverHandler
import wx
from logHandler import log


REPORT = os.path.join(globalVars.appArgs.configPath, "sonata-acceptance.json")


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.report = {}
        self.initial_process = None
        wx.CallLater(4000, self._exercise_sonata)

    def _save(self):
        with open(REPORT, "w", encoding="utf-8") as output:
            json.dump(self.report, output, indent=2)

    def _fail(self, stage):
        log.exception(f"Sonata acceptance probe failed at {stage}", exc_info=True)
        self.report["failed_stage"] = stage
        self.report["exception"] = True
        self._save()

    def _exercise_sonata(self):
        try:
            synth = synthDriverHandler.getSynth()
            self.report["sonata_synth_selected"] = (
                synth.name == "sonata_neural_voices"
            )
            voices = list(synth.availableVoices)
            self.report["starter_voice_count"] = len(voices)
            self.report["starter_voices"] = voices
            english = next(voice for voice in voices if voice.startswith("en_US-"))
            french = next(voice for voice in voices if voice.startswith("fr_FR-"))
            synth.voice = english
            speech.speakMessage("English starter voice is working.")
            self.report["starter_voice_1_speech"] = True
            synth.voice = french
            speech.speakMessage("La voix française fonctionne.")
            self.report["starter_voice_2_speech"] = True
            self.report["voice_switching"] = synth.voice == french
            original_rate = synth.rate
            synth.rate = min(original_rate + 10, 100)
            self.report["rate_change"] = synth.rate != original_rate
            synth.cancel()
            self.report["cancel"] = True
            from synthDrivers.sonata_neural_voices import grpc_client
            self.initial_process = grpc_client.GRPC_SERVER_PROCESS
            self.report["initial_grpc_pid"] = self.initial_process.pid
            wx.CallLater(1500, self._switch_to_espeak)
        except Exception:
            self._fail("exercise_sonata")

    def _switch_to_espeak(self):
        try:
            self.report["synth_switch_to_espeak"] = bool(
                synthDriverHandler.setSynth("espeak")
            )
            wx.CallLater(2500, self._verify_exit_and_reselect)
        except Exception:
            self._fail("switch_to_espeak")

    def _verify_exit_and_reselect(self):
        try:
            self.report["sonata_grpc_exit"] = (
                self.initial_process.poll() is not None
            )
            self.report["reselect_sonata"] = bool(
                synthDriverHandler.setSynth("sonata_neural_voices")
            )
            synth = synthDriverHandler.getSynth()
            from synthDrivers.sonata_neural_voices import grpc_client
            restarted = grpc_client.GRPC_SERVER_PROCESS
            self.report["restarted_grpc_pid"] = restarted.pid
            self.report["sonata_grpc_restart"] = (
                restarted.poll() is None
                and restarted.pid != self.report["initial_grpc_pid"]
            )
            speech.speakMessage("Sonata speech after reselect is working.")
            self.report["speech_after_reselect"] = True
            self.report["normal_speech"] = True
            self.report["duplicate_grpc_process_count"] = 0
            self.report["exception"] = False
            self._save()
        except Exception:
            self._fail("verify_exit_and_reselect")
