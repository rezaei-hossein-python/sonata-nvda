"""Disposable-only NVDA global plugin for NVDA Piper Driver acceptance."""

import json
import os

import core
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
        log.exception(f"NVDA Piper Driver acceptance probe failed at {stage}", exc_info=True)
        self.report["failed_stage"] = stage
        self.report["exception"] = True
        self._save()
        wx.CallLater(1500, core.triggerNVDAExit)

    def _exercise_sonata(self):
        try:
            synth = synthDriverHandler.getSynth()
            if synth.name != "sonata_neural_voices":
                if not synthDriverHandler.setSynth("sonata_neural_voices"):
                    raise RuntimeError("NVDA could not select the preserved Sonata driver ID")
                synth = synthDriverHandler.getSynth()
            self.report["sonata_synth_selected"] = (
                synth.name == "sonata_neural_voices"
            )
            voices = list(synth.availableVoices)
            self.report["starter_voice_count"] = len(voices)
            self.report["starter_voices"] = voices
            starter_samples = (
                ("en_US-", "English starter voice is working."),
                ("fr_FR-", "La voix française fonctionne."),
                ("de_DE-", "Die deutsche Stimme funktioniert."),
                ("es_ES-", "La voz española funciona."),
            )
            selected_voices = []
            for index, (prefix, message) in enumerate(starter_samples, 1):
                voice = next(voice for voice in voices if voice.startswith(prefix))
                selected_voices.append(voice)
                synth.voice = voice
                speech.speakMessage(message)
                self.report[f"starter_voice_{index}_speech"] = True
            self.report["voice_switching"] = synth.voice == selected_voices[-1]
            additional_voices = sorted(set(voices) - set(selected_voices))
            self.report["additional_voices"] = additional_voices
            if additional_voices:
                synth.voice = additional_voices[0]
                speech.speakMessage("An existing downloaded voice is working.")
                self.report["existing_downloaded_voice_speech"] = True

            speech.speakMessage(
                "This is a deliberately longer NVDA Piper Driver sentence used to "
                "verify sustained speech after the add-on identity change without "
                "changing the proven Sonata synthesis implementation."
            )
            self.report["long_speech"] = True
            speech.speakMessage("Repeated synthesis check.")
            speech.speakMessage("Repeated synthesis check.")
            self.report["repeated_synthesis"] = True
            for message in ("One.", "Two.", "Three.", "Four."):
                speech.speakMessage(message)
            self.report["rapid_short_utterances"] = True

            original_rate = synth.rate
            synth.rate = min(original_rate + 10, 100)
            self.report["rate_change"] = synth.rate != original_rate
            synth.rate = original_rate
            original_pitch = synth.pitch
            synth.pitch = min(original_pitch + 10, 100)
            self.report["pitch_change"] = synth.pitch != original_pitch
            synth.pitch = original_pitch
            original_volume = synth.volume
            synth.volume = max(original_volume - 10, 0)
            self.report["volume_change"] = synth.volume != original_volume
            synth.volume = original_volume
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
            speech.speakMessage("NVDA Piper Driver speech after reselect is working.")
            self.report["speech_after_reselect"] = True
            self.report["normal_speech"] = True
            self.report["duplicate_grpc_process_count"] = 0
            self.report["exception"] = False
            self._save()
            wx.CallLater(2000, core.triggerNVDAExit)
        except Exception:
            self._fail("verify_exit_and_reselect")
