"""Fetch and verify the pinned Piper v1.0.0 offline starter voice payload."""

import concurrent.futures
import hashlib
import json
import os
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "addon" / "starterVoices"
CATALOG_URL = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/voices.json"
)
DOWNLOAD_PREFIX = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"
SELECTION = {
    "en_US-ljspeech-medium": {
        "language": "English (United States)",
        "license": "Public domain",
        "trained_from_scratch": True,
    },
    "fr_FR-mls-medium": {
        "language": "French (France)",
        "license": "CC BY 4.0",
        "trained_from_scratch": True,
    },
    "de_DE-mls-medium": {
        "language": "German (Germany)",
        "license": "CC BY 4.0",
        "trained_from_scratch": True,
    },
    "es_ES-carlfm-x_low": {
        "language": "Spanish (Spain)",
        "license": "Public domain",
        "trained_from_scratch": True,
    },
}


def file_hash(path, algorithm):
    digest = hashlib.new(algorithm)
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(remote_path, expected, voice_dir):
    target = voice_dir / Path(remote_path).name
    if target.exists():
        if (
            target.stat().st_size == expected["size_bytes"]
            and file_hash(target, "md5") == expected["md5_digest"]
        ):
            return target
        raise RuntimeError(f"Refusing to replace unexpected existing file: {target}")
    partial = target.with_suffix(target.suffix + ".download")
    try:
        urllib.request.urlretrieve(f"{DOWNLOAD_PREFIX}/{remote_path}", partial)
        if partial.stat().st_size != expected["size_bytes"]:
            raise RuntimeError(f"Size mismatch: {remote_path}")
        if file_hash(partial, "md5") != expected["md5_digest"]:
            raise RuntimeError(f"MD5 mismatch: {remote_path}")
        os.replace(partial, target)
        return target
    finally:
        partial.unlink(missing_ok=True)


def main():
    catalog = json.load(urllib.request.urlopen(CATALOG_URL, timeout=60))
    if len(catalog) != 142:
        print(f"Note: current pinned catalog contains {len(catalog)} voices")
    jobs = []
    for key in SELECTION:
        voice_dir = TARGET / key
        voice_dir.mkdir(parents=True, exist_ok=True)
        for remote_path, expected in catalog[key]["files"].items():
            jobs.append((remote_path, expected, voice_dir))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(download_file, *job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            print(f"Verified {future.result()}")

    voices = []
    for key, metadata in SELECTION.items():
        files = []
        for path in sorted((TARGET / key).iterdir()):
            files.append({
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": file_hash(path, "sha256"),
            })
        voices.append({"key": key, **metadata, "files": files})
    manifest = {
        "schema": 1,
        "pack_version": "1.0.0",
        "catalog_url": CATALOG_URL,
        "voices": voices,
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {TARGET / 'manifest.json'}")


if __name__ == "__main__":
    main()
