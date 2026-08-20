# coding: utf-8

"""Install the bundled offline starter voices without replacing user data."""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


STARTER_PACK_DIRECTORY = Path(__file__).with_name("starterVoices")
STARTER_PACK_MANIFEST = STARTER_PACK_DIRECTORY / "manifest.json"


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(payload_dir=STARTER_PACK_DIRECTORY):
    with (Path(payload_dir) / "manifest.json").open("r", encoding="utf-8") as source:
        manifest = json.load(source)
    if manifest.get("schema") != 1 or not manifest.get("voices"):
        raise ValueError("Invalid Sonata starter voice manifest")
    return manifest


def verify_payload(payload_dir=STARTER_PACK_DIRECTORY):
    payload_dir = Path(payload_dir)
    manifest = load_manifest(payload_dir)
    for voice in manifest["voices"]:
        voice_dir = payload_dir / voice["key"]
        for file_info in voice["files"]:
            source = voice_dir / file_info["name"]
            if not source.is_file():
                raise FileNotFoundError(f"Missing starter voice file: {source}")
            if source.stat().st_size != file_info["size"]:
                raise ValueError(f"Starter voice size mismatch: {source}")
            if _sha256(source) != file_info["sha256"]:
                raise ValueError(f"Starter voice hash mismatch: {source}")
    return manifest


def install_starter_voices(payload_dir, voices_dir, logger=None):
    """Atomically install missing voices; never merge into existing directories."""
    payload_dir = Path(payload_dir)
    voices_dir = Path(voices_dir)
    manifest = verify_payload(payload_dir)
    voices_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for voice in manifest["voices"]:
        key = voice["key"]
        source = payload_dir / key
        target = voices_dir / key
        if target.exists():
            results[key] = "skipped-existing"
            continue
        temp_path = Path(tempfile.mkdtemp(prefix=f".{key}-", dir=voices_dir))
        try:
            for file_info in voice["files"]:
                shutil.copy2(source / file_info["name"], temp_path / file_info["name"])
            try:
                os.rename(temp_path, target)
            except FileExistsError:
                results[key] = "skipped-existing"
            else:
                results[key] = "installed"
                temp_path = None
        finally:
            if temp_path is not None:
                shutil.rmtree(temp_path, ignore_errors=True)
    if logger is not None:
        logger.info(f"Sonata offline starter voice installation: {results}")
    return results
