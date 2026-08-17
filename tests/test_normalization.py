import tempfile
import json
from pathlib import Path
import os
import shutil
import sys
import runpy

# Implement the normalization locally (same rules as Sonata) to test preservation semantics

def local_normalize(original_path):
    with open(original_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    needs_update = False
    if 'phoneme_map' not in data:
        data['phoneme_map'] = {}
        needs_update = True
    p_map = data.get('phoneme_id_map', {})
    invalid_keys = [k for k in p_map.keys() if len(k) > 1]
    if p_map:
        promoted = {}
        for k, v in p_map.items():
            if len(k) == 1:
                promoted[k] = v
        for k, v in promoted.items():
            if k not in data['phoneme_map']:
                data['phoneme_map'][k] = v
        if promoted != p_map:
            needs_update = True
    if needs_update:
        normalized_path = Path(original_path).with_suffix('.sonata.json')
        with open(normalized_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'), indent=2)
        if invalid_keys:
            err_path = normalized_path.with_suffix('.sonata.json.err')
            with open(err_path, 'w', encoding='utf-8') as ef:
                ef.write('\n'.join(invalid_keys))
        return str(normalized_path)
    return str(original_path)


def test_normalize_preserves_original_and_generates_sonata():
    td = Path(tempfile.mkdtemp())
    try:
        original = td / 'voice.json'
        data = {
            "name": "test",
            "phoneme_id_map": {
                "a": "ah",
                "aa": "long"
            }
        }
        with open(original, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        out = SonataVoice._normalize_config(None, str(original))
        assert out != str(original)
        sonata_path = Path(out)
        assert sonata_path.exists()
        # ensure original unchanged
        with open(original, 'r', encoding='utf-8') as f:
            orig = json.load(f)
        assert 'phoneme_id_map' in orig
        # sonata file should contain phoneme_map promoted from single-char keys
        with open(sonata_path, 'r', encoding='utf-8') as f:
            normalized = json.load(f)
        assert 'phoneme_map' in normalized
        assert 'a' in normalized['phoneme_map']
        # invalid key 'aa' should not be present and an .err file should exist
        err_path = sonata_path.with_suffix('.sonata.json.err')
        assert err_path.exists()
    finally:
        shutil.rmtree(td)
