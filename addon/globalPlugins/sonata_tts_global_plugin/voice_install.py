# coding: utf-8
"""
Lightweight generic installer helpers for Sonata voice files.
This module provides a small helper used by the harness and future UI to install
voice model+config pairs into SONATA_VOICES_DIR in a compatible layout.

Design goals:
- Create a voice directory named exactly as install_voice_from_tar_archive does
  (language-name-quality) so discovery works.
- Copy files atomically into a temporary staging directory then move into place.
- Verify file existence and return the voice_key on success.

This helper is intentionally small and compatible with existing code in voice_download.py.
"""

import os
import shutil
from pathlib import Path
import re
from .voice_download import VOICE_INFO_REGEX
from . import SONATA_VOICES_DIR


def install_voice_from_files(model_path, config_path, voices_dir=None):
    """Install a pair of model (onnx) and config (.json) files into voices_dir.

    model_path: path to .onnx file
    config_path: path to .json file
    voices_dir: target root; default SONATA_VOICES_DIR

    Returns: voice_key (folder name) on success.
    Raises: FileNotFoundError or ValueError on error.
    """
    if voices_dir is None:
        voices_dir = SONATA_VOICES_DIR
    model_path = Path(model_path)
    config_path = Path(config_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    # Derive voice_key using the same regex as tar installer
    stem = model_path.stem
    m = VOICE_INFO_REGEX.match(stem)
    if m is None:
        # try using directory name fallback
        raise ValueError(f"Could not derive voice key from model filename: {model_path.name}")
    info = m.groupdict()
    # mirror installer behavior: normalize language, replace dashes with underscore in name/quality
    # We avoid importing normalizeLanguage to keep this helper simple; expect caller to pass normalized names
    lang = info["language"]
    name = info["name"].replace("-", "_")
    quality = info["quality"].replace("-", "_")
    voice_key = "-".join([lang, name, quality])

    target_dir = Path(voices_dir).joinpath(voice_key)
    tmp_dir = target_dir.parent.joinpath(voice_key + ".staging")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(model_path, tmp_dir.joinpath(model_path.name))
        shutil.copy2(config_path, tmp_dir.joinpath(config_path.name))
        # If model card exists alongside model, copy it too (optional)
        model_card = model_path.with_name("MODEL_CARD")
        if model_card.exists():
            shutil.copy2(model_card, tmp_dir.joinpath("MODEL_CARD"))
        # Move staging folder into final location atomically if possible
        if target_dir.exists():
            # already installed; replace contents atomically by removing and renaming
            shutil.rmtree(target_dir)
        os.replace(str(tmp_dir), str(target_dir))
    except Exception:
        # cleanup
        try:
            if tmp_dir.exists():
                shutil.rmtree(tmp_dir)
        except Exception:
            pass
        raise
    return voice_key
