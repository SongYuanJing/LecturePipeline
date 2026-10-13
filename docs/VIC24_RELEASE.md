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

## 2026-10-13 checkpoint: prepublish passed, public acceptance blocked

- Release source/build commit: `a57d75dc8e820780eeeacdbdbfcae13c12980bdd`.
  Branch and new annotated `v2.0.0-beta.1` tag pushed without force.
- 78 targeted Python tests passed, including release payload, updater failure/rollback,
  resumable downloads and DPI coverage; 22 .NET bootstrap assertions passed.
- Exact Setup: 51,854,062 bytes, SHA-256
  `95091d623a381dbed4d0f1f28c9e0230bbff3277f0ff761581511e44b92921c2`.
- Exact code-only update ZIP: 139,139 bytes, SHA-256
  `a7e1ffeaecd552473d24f4c481d30d3610200832703fd545a234a6babb4ee109`.
  Its six runtime contract hashes match the public old beta.2 manifest.
- Local prepublish Setup passed using newly downloaded suppliers: all component
  imports valid, Auto selected cuda, ready report produced. The installed shortcut
  reopened the real `Lecture Pipeline · 2.0.0-beta.1` GUI and normal close worked.
  No GUI log errors. A prior window close reported by the user has no recorded
  cause; successful reopen must not be presented as a diagnosis of that close.
- Initial GUI displays missing worker-status paths before workers first run;
  recorded as existing UX noise, not an installation error.
- GitHub publication is **NOT complete**. Six small assets reached a draft; the
  Setup upload produced no asset after over ten minutes. That exact upload process
  was stopped; one upload-only retry likewise produced no asset after over five
  minutes and was stopped. Neither command supplied an HTTP error before the
  bounded stop. Do not claim a 403/auth defect or publish the incomplete draft.
- Public fresh-install and beta.2-to-v2 upgrade acceptance remain **pending**.
  Do not move the tag, overwrite assets, or label VIC-24 Done. Resume by inspecting
  the existing draft and uploading only the missing exact Setup, then publishing
  only after all asset sizes/hashes match. No additional product changes were made.
- Five representative protected production/baseline files retained both SHA-256
  and mtime. No operational course/Google Drive paths were used.

Local operator evidence (not release content): `.local/vic24/prepublish.json`,
`draft-release.json`, `protected-check.json`, `checkpoint.md`, targeted build/test
logs. Disposable prepublish root: `%TEMP%/LP24-1013P`; separate public old-beta setup
root: `%TEMP%/LP24-Upgrade`. Inspect its `setup-result.json` before continuing; never
assume an interrupted process remained alive. Verified supplier caches stay there.
