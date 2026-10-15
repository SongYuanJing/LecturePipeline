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

## 2026-10-14 publication and upgrade checkpoint

The transport blocker is resolved without rebuilding or replacing assets. HTTPS
HEAD reached uploads.github.com. An HTTP/1.1 curl upload timed out at 180 seconds
after transmitting 38,813,408 bytes; a bounded 420-second retry completed with
HTTP 201, all 51,854,062 bytes, in 278.869 seconds. No auth/403 error was observed.
The existing draft's six small assets were verified and preserved. All seven
server-side sizes/digests matched; the draft was published as prerelease, then all
seven public assets were downloaded again and their local SHA-256/size verified.

Release: https://github.com/SongYuanJing/LecturePipeline/releases/tag/v2.0.0-beta.1
Tag/source remains a57d75dc8e820780eeeacdbdbfcae13c12980bdd. No rebuild, version
change, tag movement or replacement of correct assets occurred.

The separate public beta.2 candidate completed real GitHub discovery/download,
manifest/ZIP verification, stage/health, atomic switch and first launch to v2.
Its real GUI displayed v2, Preflight OK, AUTO to GPU and "Установлена последняя
версия" after Check Updates. Four initialized config/data files retained exact
SHA-256 and mtime; old version retained; no pending transaction. This is minimal
legacy initialized state, not a migration of real study data. The old stable
launcher remained unchanged, including its documented VIC-20 limitation.
Two bounded fixture rollback tests passed again (staged health rejection and
failed first-launch pointer restore); the sandbox-only Temp permission failure
was superseded by the normal disposable Windows Temp run, not a product fix.

Evidence: `.local/vic24/expected-assets.json`, `verified-release.json`,
`transport-20261014.json`, `upgrade-discovery.log`, `upgrade-apply.log`,
`upgrade-invariance.json`, `upgrade-result.json`, `rollback-smoke-native-temp.log`.
Fresh published Setup acceptance continues at `%TEMP%/LP24-Public-1014`;
functional acceptance is not yet claimed.

## 2026-10-14 fresh public install: Unicode integration defect

The resumed public candidate at `%TEMP%/LP24-Public-1014` had already completed
Setup: ready report, all pinned components imported, no partial downloads, native
Auto selected `cuda` (`int8_float16`). The installed shortcut reopened the actual
`2.0.0-beta.1` GUI. No supplier downloads or prior update gates were repeated.

The existing `Integrate.cmd -Apply` passed native preflight but failed assigning
WScript shortcut TargetPath for the Chinese installation path: `Value does not
fall within the expected range` at Integrate.ps1 line 41. The failure was reproduced
without saving a shortcut: ASCII target accepted, the existing Chinese paths
rejected. Newly registered disposable tasks rolled back (zero matching tasks
remain). Six pre-existing task XML definitions remain identical. Five representative
protected production/baseline files retain both SHA-256 and mtime.

Local fix `50b9187` shares the existing Setup `IShellLinkW` implementation with
Integrate, using Windows PowerShell-compatible C# syntax. No second shortcut
implementation, updater change, runtime migration or config contract change.
Native Unicode shortcut create/read regression passed under Windows PowerShell;
targeted first-run/payload checks: **7 passed, 1 explicitly skipped** (deployment
plan test needs a configured test deployment). **22 bootstrap assertions passed**.
These are local fix tests, not public fresh-install acceptance of the fix.

The public beta.1 installation and published assets/tag are not patched or replaced.
The fix requires a forward beta.2 build and affected integration/public fresh-flow
validation. No version bump or beta.2 release was made at this checkpoint.
GUI automation subsequently could not activate the existing window; no course was
saved, no single/multipart ASR, manual AI/Word or restart acceptance is claimed.
VIC-24 remains **not Done**, and VIC-20 final closure remains conditional on the
remaining acceptance. Earlier evidence that fresh Setup includes its updater UX
fix remains valid; legacy code-only update still retains the old launcher.

Evidence: `.local/vic24/fresh-integration.log`,
`unicode-shortcut-first-run.log`, `unicode-shortcut-payload.log`,
`unicode-shortcut-bootstrap.log`, `tasks-after-integration-failure.json`,
`protected-after-integration-failure.json`; candidate `setup-result.json` and
`App 课程/logs/bootstrap-health.json`. Continue from these artifacts; do not rerun
the completed public asset/old-beta update/rollback gates without a changed risk.

## Public beta.2 course-save checkpoint (2026-10-15)

Public beta.2 source is `42b74644d9c61bf7efebe75c7e8953db8f3f36fa`.
Publication, independent public asset verification, Unicode Integrate and the
beta.1-to-beta.2 update gates have completed (evidence under
`.local/vic24/beta2/`). The existing disposable public install resumed to ready,
native Auto selected CUDA, and the main GUI started. No repeated supplier import
or replacement of the published installed code was used.

The next real GUI course save exposed a separate fresh-install defect:
`WorkerControl.ps1 -Action Stop` attempts to write `worker.stop` before the
never-started worker home exists. Config transaction evidence reports
`rolled_back`; the saved config still contains only the default subject.
The same missing-parent assumption exists in DialogueControl. Local fix creates
only the resolved worker home before Stop/ForceStop/Uninstall. No task identity,
config schema, launcher or processing contract changes.

Validation: one native Windows PowerShell test covers both controllers and all
three actions (six subcases, each repeated twice), with Scheduler functions
substituted and real disposable stop files. PASS. Existing course setup suite:
15 PASS. An initial sandbox execution failed on Temp permissions before testing
the product; the authorized native rerun passed.

Evidence: `public-course-save-failure.log`, `public-course-save-failure.json`,
`public-fresh-checkpoint.json` under the above local evidence directory.
The public beta.2 installation/assets/tag remain unchanged. This local fix is
not public acceptance; delivery needs a forward release, not replacement of
beta.2. Single/multipart ASR, manual AI/Word, restart and final GUI update check
remain pending. VIC-24 and final VIC-20 closure remain open.

During manual entry a Drive path was selected before the requested Temp correction.
Directory validation precedes the failed worker stop, so absence of Drive folder
creation cannot be claimed. No Drive cleanup or inspection was performed by the
agent; no audio was submitted there. Do not treat this as a protected-root PASS.
