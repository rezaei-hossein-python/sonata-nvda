import os
import subprocess
import shutil
import zipfile
import glob
import sys

# Pinned dependency set for Sonata NVDA AMD64 Python 3.13
DEPENDENCIES = [
    "grpcio==1.83.0",
    "protobuf==7.35.1",
    "typing_extensions==4.16.0",
    "miniaudio==1.71",
    "cffi==2.1.1",
    "psutil==7.2.2"
]

STAGING = "vendor_staging"
LIB_DIR = os.path.join("..", "addon", "synthDrivers", "sonata_neural_voices", "lib")

def fail(msg):
    print("ERROR:", msg, file=sys.stderr)
    sys.exit(1)

def build_vendor():
    # deterministic staging
    if os.path.exists(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(STAGING)

    print("Downloading exact Python 3.13 AMD64 wheels...")
    cmd = [
        "pip", "download", "--only-binary=:all:", "--platform", "win_amd64",
        "--python-version", "3.13", "--implementation", "cp", "--abi", "cp313",
        "-d", STAGING
    ] + DEPENDENCIES

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        fail(f"pip download failed: {e}")

    wheels = sorted(glob.glob(os.path.join(STAGING, "*.whl")))
    if not wheels:
        fail("No wheels downloaded; check network and pip availability.")

    # Validate wheel filenames to ensure correct platform and Python tag
    for w in wheels:
        name = os.path.basename(w)
        if "win_amd64" not in name or ("cp313" not in name and "cp3" not in name):
            fail(f"Unexpected wheel found in staging: {name}. Aborting to avoid mixing architectures.")

    # Recreate lib dir cleanly
    if os.path.exists(LIB_DIR):
        shutil.rmtree(LIB_DIR)
    os.makedirs(LIB_DIR)

    # Extract each wheel into lib dir
    for whl in wheels:
        print(f"Extracting {os.path.basename(whl)}...")
        with zipfile.ZipFile(whl, 'r') as z:
            z.extractall(LIB_DIR)

    # Remove metadata and wheel-extraction leftovers deterministically
    for pattern in ("*.dist-info", "*.data", "WHEEL-INFO", "RECORD"):  # patterns used during wheel extraction
        for path in glob.glob(os.path.join(LIB_DIR, pattern)):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception:
                pass

    # Prune bytecode caches and ensure no platform-mismatched artifacts remain
    for root, dirs, files in os.walk(LIB_DIR):
        if "__pycache__" in dirs:
            try:
                shutil.rmtree(os.path.join(root, "__pycache__"))
            except Exception:
                pass

    # Final sanity: ensure no win32 / cp311 / cp37 artifacts remain
    leftovers = []
    for p in glob.glob(os.path.join(LIB_DIR, "**", "*cp311*"), recursive=True):
        leftovers.append(p)
    for p in glob.glob(os.path.join(LIB_DIR, "**", "*win32*"), recursive=True):
        leftovers.append(p)
    if leftovers:
        fail(f"Found unexpected leftover artifacts after extraction: {leftovers[:5]} (truncated)")

    # Cleanup staging
    shutil.rmtree(STAGING)
    print("Vendor lib populated successfully with Python 3.13 AMD64 binaries.")

if __name__ == "__main__":
    build_vendor()
