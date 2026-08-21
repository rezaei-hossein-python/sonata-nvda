# Changelog

## 3.2.1

- Automatically detects Sonata Neural Voices 3.1.1 during installation and
  schedules it for removal with NVDA's supported `Addon.requestRemove()`
  lifecycle.
- Leaves other Sonata versions installed for manual review.
- Preserves the shared `<NVDA configPath>\sonata\voices\piper` voice library
  byte-for-byte during migration.
- Deploys bundled starter voices only for genuinely fresh installations;
  migration and same-ID updates make zero changes to the existing voice tree.
- Adds executable fresh-install, migration and same-ID update tests covering
  detection, idempotence, repeated callbacks, failure handling and voice-data
  preservation.

## 3.2.0

- Established the distinct NVDA Piper Driver identity for the maintained NVDA
  2026 AMD64 / CPython 3.13 adaptation of Sonata Neural Voices.
- Preserved the proven Sonata runtime, four offline starter voices, Voice
  Manager and existing local voice library.
