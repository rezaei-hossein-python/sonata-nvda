"""Verify staged starter voice blobs against the staged manifest."""

import hashlib
import json
import subprocess


def staged_bytes(path):
    return subprocess.check_output(["git", "show", f":{path}"])


def main():
    manifest = json.loads(staged_bytes("addon/starterVoices/manifest.json"))
    mismatches = []
    for voice in manifest["voices"]:
        for file_info in voice["files"]:
            path = f"addon/starterVoices/{voice['key']}/{file_info['name']}"
            content = staged_bytes(path)
            if len(content) != file_info["size"]:
                mismatches.append((path, "size"))
            elif hashlib.sha256(content).hexdigest() != file_info["sha256"]:
                mismatches.append((path, "sha256"))
    print(f"STAGED_STARTER_PAYLOAD_MISMATCHES = {mismatches}")
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
