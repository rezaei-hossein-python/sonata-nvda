import sys
from pathlib import Path

driver_path = Path(__file__).resolve().parents[1] / 'addon' / 'synthDrivers' / 'sonata_neural_voices'
lib_path = driver_path / 'lib'
assert lib_path.exists(), f"Vendored lib path missing: {lib_path}"
# Add vendored lib to sys.path for import tests
sys.path.insert(0, str(lib_path))

def test_imports():
    import importlib
    modules = ['grpc', 'google.protobuf', 'cffi', 'miniaudio', 'psutil', 'typing_extensions']
    for m in modules:
        importlib.import_module(m)


def test_native_architectures():
    # Ensure native binaries are present and are x64
    import struct
    import glob
    import os
    patterns = ['**/*.pyd', '**/*.dll', '**/*.exe']
    found = []
    for p in patterns:
        found.extend(glob.glob(str(driver_path / p), recursive=True))
    assert found, 'No native binaries found in synth driver'
    def arch_of(path):
        with open(path, 'rb') as fh:
            mz = fh.read(64)
            assert mz[:2] == b'MZ'
            fh.seek(0x3c)
            e_lfanew = struct.unpack('<I', fh.read(4))[0]
            fh.seek(e_lfanew)
            hdr = fh.read(6)
            assert hdr[:4] == b'PE\x00\x00'
            machine = struct.unpack('<H', hdr[4:6])[0]
            return machine
    for f in found:
        machine = arch_of(f)
        assert machine in (0x8664,), f"Found non-x64 binary: {f} (machine=0x{machine:x})"


test_imports()
test_native_architectures()
