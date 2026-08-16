# NVDA 2026.1+ AMD64 Port

This port upgrades Sonata Neural Voices for NVDA 2026.1+ (AMD64) and Python 3.13.

## Differences from Upstream 3.1.0
- Replaced 32-bit (x86) Python `.pyd` dependencies with strictly matched `win_amd64` CP313 binaries.
- Automatically normalizes Lessac/Piper voice configurations at runtime (`.sonata.json`) if they contain multi-byte Unicode phoneme keys or lack the `phoneme_map` required by the Rust `sonata-grpc` parser. This is non-destructive to original models.
- Uses a reproducible vendor script (`tools/build_vendor_lib.py`) for maintaining exact dependencies.
- Added `typing_extensions` for Python 3.13 gRPC compatibility.
- Added a pure-Python fallback for `msgfmt` compilation during add-on build.

## Building
1. Run `python tools/build_vendor_lib.py` to stage AMD64 dependencies.
2. Run `python -m SCons` to build the `.nvda-addon` package.

## Known Limitations
Currently targets 64-bit strictly. Reverting to 32-bit requires regenerating the `lib/` directory with `win32` wheels.
