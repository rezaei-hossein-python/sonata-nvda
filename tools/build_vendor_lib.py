import os
import subprocess
import shutil
import zipfile
import glob

DEPENDENCIES = [
    "grpcio==1.83.0",
    "protobuf==7.35.1",
    "typing_extensions==4.16.0",
    "miniaudio==1.71",
    "cffi==2.1.1",
    "psutil==7.2.2"
]

def build_vendor():
    staging = "vendor_staging"
    if os.path.exists(staging): shutil.rmtree(staging)
    os.makedirs(staging)
    
    print("Downloading exact Python 3.13 AMD64 wheels...")
    cmd = [
        "pip", "download", "--only-binary=:all:", "--platform", "win_amd64",
        "--python-version", "3.13", "--implementation", "cp", "--abi", "cp313",
        "-d", staging
    ] + DEPENDENCIES
    subprocess.run(cmd, check=True)
    
    lib_dir = os.path.join("..", "addon", "synthDrivers", "sonata_neural_voices", "lib")
    if os.path.exists(lib_dir): shutil.rmtree(lib_dir)
    os.makedirs(lib_dir)
    
    for whl in glob.glob(os.path.join(staging, "*.whl")):
        print(f"Extracting {os.path.basename(whl)}...")
        with zipfile.ZipFile(whl, 'r') as z:
            z.extractall(lib_dir)
            
    # Cleanup metadata
    for dist in glob.glob(os.path.join(lib_dir, "*.dist-info")):
        shutil.rmtree(dist)
    shutil.rmtree(staging)
    print("Vendor lib populated successfully with Python 3.13 AMD64 binaries.")

if __name__ == "__main__":
    build_vendor()
