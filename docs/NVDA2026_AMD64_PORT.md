# NVDA 2026.1+ AMD64 Port

This port upgrades Sonata Neural Voices for NVDA 2026.1 (AMD64) and Python 3.13.
Release 3.1.1 was validated with NVDA 2026.1.1. Later NVDA releases are not
claimed until they have been tested.

## Differences from Upstream 3.1.0
- Replaced 32-bit (x86) Python `.pyd` dependencies with strictly matched `win_amd64` CP313 binaries.
- Preserves upstream Sonata voice configuration and synthesis behavior without runtime normalization.
- Uses a reproducible vendor script (`tools/build_vendor_lib.py`) for maintaining exact dependencies.
- Added `typing_extensions` for Python 3.13 gRPC compatibility.
- Added a pure-Python fallback for `msgfmt` compilation during add-on build.

## Building
1. Run `python tools/build_vendor_lib.py` to stage AMD64 dependencies.
2. Run `scons -Q` to build the `.nvda-addon` package.

## Known Limitations
Currently targets 64-bit strictly. Reverting to 32-bit requires regenerating the `lib/` directory with `win32` wheels.
