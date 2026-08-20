"""Exercise Sonata's remote MP3 preview chain outside NVDA."""

import json
import os
import sys
import tempfile
import wave
import winsound
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "addon/synthDrivers/sonata_neural_voices/lib"
sys.path.insert(0, str(LIB))

import miniaudio  # noqa: E402
import mureq  # noqa: E402


URLS = {
    "english": (
        "https://rhasspy.github.io/piper-samples/samples/"
        "en/en_US/ljspeech/medium/speaker_0.mp3"
    ),
    "french": (
        "https://rhasspy.github.io/piper-samples/samples/"
        "fr/fr_FR/siwis/low/speaker_0.mp3"
    ),
}


def validate(name, url):
    result = {
        "preview": name,
        "url": url,
        "http_status": None,
        "downloaded_bytes": 0,
        "mp3_decode": False,
        "audio_output": False,
        "exception": None,
    }
    try:
        response = mureq.get(url, max_redirects=10, timeout=30)
        result["http_status"] = response.status_code
        response.raise_for_status()
        result["downloaded_bytes"] = len(response.body)
        decoded = miniaudio.decode(response.body, nchannels=1, sample_rate=22050)
        result["mp3_decode"] = len(decoded.samples) > 0
        with tempfile.TemporaryDirectory() as tempdir:
            wav = os.path.join(tempdir, f"{name}.wav")
            with wave.open(wav, "wb") as wav_output:
                wav_output.setnchannels(decoded.nchannels)
                wav_output.setsampwidth(decoded.sample_width)
                wav_output.setframerate(decoded.sample_rate)
                wav_output.writeframes(decoded.samples.tobytes())
            winsound.PlaySound(wav, winsound.SND_FILENAME)
            result["audio_output"] = True
    except Exception as error:
        result["exception"] = f"{type(error).__name__}: {error}"
    return result


def main():
    results = [validate(name, url) for name, url in URLS.items()]
    failure = validate(
        "expected_failure",
        "https://rhasspy.github.io/piper-samples/samples/not-a-voice.mp3",
    )
    results.append(failure)
    print(json.dumps(results, indent=2))
    if not all(
        result["http_status"] == 200
        and result["downloaded_bytes"] > 0
        and result["mp3_decode"]
        and result["audio_output"]
        and result["exception"] is None
        for result in results[:2]
    ):
        raise SystemExit(1)
    if failure["exception"] is None:
        raise SystemExit("Expected HTTP failure was not reported")


if __name__ == "__main__":
    main()
