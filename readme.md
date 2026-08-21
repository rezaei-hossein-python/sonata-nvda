# NVDA Piper Driver

## Overview

NVDA Piper Driver provides fast, local neural text-to-speech for NVDA using
Piper voice models through the proven Sonata engine. This maintained fork is an
NVDA 2026 AMD64 and CPython 3.13 adaptation of **Sonata Neural Voices**, which
was originally developed by Musharraf Omer.

This release changes the public add-on identity without rewriting Sonata's
synthesis implementation. The internal Sonata driver and data paths remain in
place for compatibility with existing voices and settings.

## Features

- Local neural Piper speech after a voice is installed.
- Four bundled multilingual starter voices that work without Internet access.
- An accessible Voice Manager for browsing, previewing, installing and removing
  voices.
- Additional multilingual voices from the existing Piper catalog.
- Standard and fast/RT variants where the selected catalog voice provides them.
- A hidden, managed `sonata-grpc.exe` backend with clean synth switching and
  shutdown.

## Compatibility

Version 3.2.1 is built and tested for **NVDA 2026.1.1 on 64-bit Windows**. It
contains AMD64 native dependencies for NVDA's CPython 3.13 runtime. Compatibility
with later NVDA releases or 32-bit Windows is not claimed.

## Installation

1. Download `nvdaPiperDriver-3.2.1.nvda-addon` from the
   [v3.2.1 release](https://github.com/rezaei-hossein-python/sonata-nvda/releases/tag/v3.2.1).
2. Open the package and approve installation in NVDA.
3. Restart NVDA when prompted.
4. Open NVDA's speech settings and select **NVDA Piper Driver**.

## Bundled offline voices

The package includes these validated starter voices:

- English: `en_US-ljspeech-medium`
- French: `fr_FR-mls-medium`
- German: `de_DE-mls-medium`
- Spanish: `es_ES-carlfm-x_low`

On a genuinely fresh installation, these four voices are installed locally and
can be used immediately without downloading a voice. Starter deployment is
skipped during migration from Sonata Neural Voices and during updates from an
existing NVDA Piper Driver installation. This prevents an update from adding
anything to an established voice library. Existing voice files and directories
are never overwritten or merged.

## Selecting NVDA Piper Driver and changing voices

Select **NVDA Piper Driver** from NVDA's synthesizer list. Use the Voice control
in NVDA's speech settings or synthesizer settings ring to select an installed
voice. Speaker, rate, pitch, volume and model controls remain available where
the voice supports them.

## Voice Manager

Open NVDA's main menu and choose **NVDA Piper Driver voice manager**. The
Installed tab lists local voices and can install a compatible local voice
archive or remove a voice that is not currently active.

The Online tab retrieves the existing Piper catalog. You can browse voices by
language and quality, listen to a preview, and install a standard or available
fast variant. Downloads are validated and installed atomically.

## Internet and offline behavior

Internet access is needed for:

- refreshing the online catalog;
- listening to online previews; and
- downloading new voices.

Normal synthesis does not require Internet access once a voice is installed.
Bundled starter voices and voices installed through Voice Manager remain usable
offline.

## Voice variants

Some catalog entries offer both a standard model and a separate fast/RT model.
The fast variant can improve responsiveness with a possible quality trade-off.
Variants are shown only when the catalog and installed model files actually
provide them.

## Existing Sonata Neural Voices 3.1.1 users

NVDA Piper Driver uses a new add-on ID. When version 3.2.1 is installed, it
detects Sonata Neural Voices 3.1.1 and schedules that exact legacy release for
removal through NVDA's supported add-on lifecycle. Restart NVDA to complete the
migration. Removing the old add-on does not remove installed voices, and the
shared local voice library is never moved or rewritten by the migration.

Bundled starter deployment is skipped during this migration. Existing users
keep exactly the voice library they had before installation; missing starter
voices are not silently added.

Only Sonata Neural Voices 3.1.1 is removed automatically. Any other Sonata
version is left installed for manual review rather than being removed by an
assumption.

The internal synthesizer ID remains `sonata_neural_voices`. After migration,
reselect **NVDA Piper Driver** in NVDA's speech settings if necessary.

## Voice storage

Installed voices are stored under:

```text
<NVDA configPath>\sonata\voices\piper
```

This path is intentionally unchanged so existing downloaded voices remain
available after upgrading or rebranding.

## Updating and uninstalling

Install a newer package over NVDA Piper Driver when an update is available and
restart NVDA. Updates skip bundled starter deployment and leave the existing
voice tree byte-for-byte unchanged. To uninstall, use NVDA's Add-on Store or
Add-on Manager and restart NVDA. Uninstalling the add-on leaves the shared local
voice directory intact; voices may be removed separately through Voice Manager
or manually by the user.

## Characteristics and limitations

- Neural voice responsiveness and pronunciation depend on the selected model,
  language and quality level.
- Low and medium models are usually more responsive than high-quality models.
- Online catalog, preview and download features naturally require network
  access.
- The bundled backend is for 64-bit Windows and is not a 32-bit build.

## Original project and attribution

NVDA Piper Driver is a maintained adaptation of
[Sonata Neural Voices](https://github.com/mush42/sonata-nvda), originally
created by **Musharraf Omer**. The Sonata engine, Piper-related components,
third-party native libraries and bundled voice models retain their original
notices, model cards and license material. This fork does not claim original
authorship of Sonata.

## Maintainer and source

- Current fork maintainer: **Hosein Rezaii**
- Contact: **rezaii.hosein@gmail.com**
- Maintained source: <https://github.com/rezaei-hossein-python/sonata-nvda>
- Original upstream: <https://github.com/mush42/sonata-nvda>

## Licensing

The add-on is distributed under the GNU General Public License version 2. See
`COPYING.txt`. Third-party notices are retained under
`addon/synthDrivers/sonata_neural_voices/bin/NOTICES`, and each bundled starter
voice includes its Piper `MODEL_CARD`. See `addon/starterVoices/LICENSES.md` and
`addon/starterVoices/manifest.json` for voice provenance, licensing and hashes.
