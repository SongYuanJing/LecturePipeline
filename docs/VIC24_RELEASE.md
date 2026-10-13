# VIC-24 release engineering — v2.0.0-beta.1

Starting validated source: `08317a66095bc44bc78db2c3dc0666fef625c605`, branch
`feature/course-setup-gui`. Acceptance is pending; no claim of a published/accepted
v2 release until fresh public install and old-beta upgrade gates complete.

## Audited release architecture

- Canonical application version: `scripts/build_package.py:VERSION`.
- Bootstrap payload imports that version and supplies `current.json`, versioned
  code, `release.json` hashes, launcher and pinned supplier manifests. Setup remains
  self-contained .NET 10 win-x64. File/product version derives from the payload.
- Private base remains the existing immutable v1.9.5-beta.1 asset, pinned by SHA
  and size in `bootstrap/base.json`; new payload replaces staged code/launcher.
  The base's old release name is deliberate runtime reuse, not an update feed.
- Update archive remains code-only, built by `scripts/build_update.py`; manifest
  schema/protocol 1, config schema 1, no migration. Existing runtime contract hashes
  must match the old public beta.2. No major-version compatibility relaxation.
- Existing semantic parser accepts `2.0.0-beta.1` and orders it after `1.9.7-beta.2`.
  A prerelease installation discovers newer tagged prereleases; stable users do
  not opt into beta automatically. Main is never an update feed.
- Packaged config diagnostics read the version's release manifest. Historical
  component/layer versions (ASR 1.3, Word AI 1.5) are not application versions.
- Public beta.2 assets still exist, including Setup and the update manifest/ZIP.
  The known GUI updater build/publication workflow is reused.

## VIC-20 boundary

Commit `cd13686` semantics exist in both source GUI update checks and the stable
launcher progress window. Fresh v2 Setup includes both. A code-only upgrade from
old beta.2 cannot replace `launcher/update_gui.py`; that old install retains its
verbose staged-health failure presentation. Do not claim the old stable launcher
was upgraded, and do not add launcher migration in this release task. Record this
distinction in acceptance and release notes; new GUI check error messages are in
the updated versioned code. VIC-20 completion remains subject to published-build
proof, with this legacy-launcher limitation explicitly disclosed.

## Safety / gate order

New disposable install/data roots only. No changes to production, baseline, working
Beta, old tags/releases, university/Drive course roots. Build from a clean commit;
inspect exact artifacts and run local Setup smoke before publishing. Afterward,
download public assets, fresh-install/short actual-ASR/manual-AI/Word/catalog smoke,
restart, and separate public beta.2 → v2 update with config/data fingerprints.
No VIC-15, signing, runtime migration or release overwrite. Fix public defects
forward as beta.2 rather than moving a tag.
