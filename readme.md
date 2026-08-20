# Sonata Neural Voices for NVDA

Sonata Neural Voices adds fast, local neural text-to-speech to NVDA using
[Piper voice models](https://github.com/rhasspy/piper) through the
[Sonata engine](https://github.com/mush42/sonata).

This repository is a maintained NVDA 2026 AMD64 adaptation of the original
[Sonata NVDA add-on](https://github.com/mush42/sonata-nvda) by Musharraf Omer.
It updates the native dependencies for 64-bit NVDA and CPython 3.13 while
preserving the original Sonata synthesis design.

## Compatibility

Version 3.1.1 was tested with NVDA 2026.1.1 on 64-bit Windows. Its manifest
requires NVDA 2026.1 or later. Compatibility with 32-bit NVDA, older NVDA
releases, ARM64 Windows, or later experimental NVDA releases has not been
claimed or tested.

## Installation

1. Download `sonata_neural_voices-3.1.1.nvda-addon` from the
   [v3.1.1 release](https://github.com/rezaei-hossein-python/sonata-nvda/releases/tag/v3.1.1).
2. Open the downloaded file and confirm installation in NVDA.
3. Restart NVDA when prompted.
4. Select **Sonata Neural Voices** in NVDA's speech settings.

Updating from another build uses NVDA's normal add-on installation process.
The installer does not overwrite an existing voice directory with different
bytes.

## Offline starter voices

The add-on includes four voices that are installed locally with the package:

- English: `en_US-ljspeech-medium`
- French: `fr_FR-mls-medium`
- German: `de_DE-mls-medium`
- Spanish: `es_ES-carlfm-x_low`

These starter voices work without an Internet connection after installation.
Their original Piper model cards and license information are included in the
package. See [the starter voice license inventory](addon/starterVoices/LICENSES.md)
for sources and attribution.

## Sonata Voice Manager

Open NVDA's main menu and choose **Sonata Voice Manager**. The manager can:

- list the online Piper voice catalog;
- preview catalog voices before installation;
- download and install additional languages and voices;
- remove installed voices; and
- install a compatible local voice archive.

Previewing and downloading catalog voices requires Internet access. Normal
synthesis does not require Internet access once a voice has been installed.

Low- and medium-quality models usually offer a useful balance between speech
quality, storage, and responsiveness. Where the catalog provides both
variants, the standard variant favors quality and the fast variant favors
responsiveness at some cost to speech quality.

After adding or removing voices, restart NVDA if the available voice list does
not refresh immediately.

## Uninstalling or updating

Use NVDA's Add-on Store or Add-on Manager to disable, update, or remove Sonata
Neural Voices, then restart NVDA. Voice files downloaded into the NVDA user
configuration may remain so that an add-on update does not destroy user data.
Use Sonata Voice Manager to remove voices you no longer want. The bundled
starter voices are offered again on a later installation only when their target
directories do not already exist.

## Characteristics and limitations

- Neural voices use more disk space and CPU than NVDA's built-in eSpeak NG.
- Responsiveness varies with model quality and computer performance.
- Pronunciation and audio quality reflect the datasets used to train each
  voice and may vary between languages and speakers.
- Online catalog previews and downloads depend on third-party Piper hosting;
  already installed voices remain usable offline.
- This maintained build currently targets Windows AMD64 only.

## Project history and support

Musharraf Omer created the original Sonata project and Sonata NVDA add-on. This
NVDA 2026 AMD64 / CPython 3.13 adaptation is maintained by Hosein Rezaii
<rezaii.hosein@gmail.com>. Please report fork-specific problems at the
[maintained repository](https://github.com/rezaei-hossein-python/sonata-nvda/issues).
The [original upstream repository](https://github.com/mush42/sonata-nvda)
remains documented for attribution and project history.

## Licensing

The add-on source remains licensed under GNU GPL v2; see [COPYING.txt](COPYING.txt).
Copyright and original-author notices are preserved. Bundled native components
retain their own license notices under `addon/synthDrivers/sonata_neural_voices/bin/NOTICES`.
Bundled voice models are separate data works and retain their model cards and
individual license terms.
