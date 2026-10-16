# VIC-24 final acceptance — 2026-10-16

Status: **Done**. VIC-20: **Done**, with the legacy launcher boundary below.
This closes the accepted functional checkpoint plus final visual inspection;
it does not claim a new cold beta.4 install or repeat of expensive tests.

## Release and source

- Branch: `feature/course-setup-gui`.
- Published release: https://github.com/SongYuanJing/LecturePipeline/releases/tag/v2.0.0-beta.4
- Release source / locally peeled tag: `d2c9ee0aad6ec55ed54936dbd4323ac9923f0523`.
- Product fixes: `22567ff` (missing optional heartbeat observation) and
  `4f154a26f6053425ec890a2fe4611a70a34edf79` (document-runtime validation).
- All seven public assets were downloaded back and verified before this closeout;
  retained downloads were rechecked against the accepted manifest. Exact inventory:
  [vic24-beta4-assets.json](vic24-beta4-assets.json).
- Setup: 51,855,651 bytes; SHA-256
  `d324edfb3d22c4751efed01a4930b287d1d720332a1f064e369158e4bc82d512`.
- Final live GitHub metadata/tag refresh was unavailable due to DNS resolution
  failure, not authentication. Publication/public-download evidence from the
  completed gate is retained; no tags/assets were altered during closeout.

## Accepted functional evidence (reused, not rerun)

Existing public installation `%TEMP%/LP24-B3-Public/App 课程` and its existing
Course/data were used throughout. No new roots or model/CUDA downloads.

- Public beta.3 fresh bootstrap, first-Course save regression, Unicode shortcut
  and isolated task integration passed before the forward beta.4 update.
- Single and multipart 3/1/2 fixtures completed real large-v3 CUDA ASR. Multipart
  was one lecture ordered 1/2/3. Raw/TXT/SRT and duplicate suppression passed.
- Current manual-compatible synthetic AI results produced both Word documents,
  vocabulary and completion records. No AI API/quality claim is made.
- Real beta.3 → beta.4 updater: tagged discovery, network download, manifest/SHA
  validation, side-by-side stage, health, atomic pointer switch and first GUI
  readiness all passed. beta.3 remains retained; no pending transaction.
- All 47 config/data files retained SHA-256 and mtime through update.
- Installed ASR Python has no python-docx; beta.4 successfully validated both
  existing Word files through document Python and recovered both queue entries
  to completed. Catalog shows Done with no stale progress. Native check: 3.218 s.
- Word opening from GUI was manually confirmed by the user.
- Integrate.cmd -Apply passed. GUI reopened through the installed shortcut.
- Worker restart revalidated both DONE lectures and ignored duplicate READY;
  no new ASR/Raw/Word. Only two expected WORKER_STATUS observations changed.
- Before update, stopping the newly started disposable Dialogue worker created
  four service observation/state files; original 43 files were unchanged. Both
  pre-stop and immediate pre-update baselines were retained, not conflated.
- Final updater check: current beta.4, tag null, status no-update.
- Targeted beta.4 tests already passed: 75 (16 finalizer, 4 fresh-status,
  13 updater, 2 update-contract, 7 update-GUI, 2 payload, 31 catalog).

## Final visual closeout

Inspected the already reopened actual main window (window 592772), without
restarting or reprocessing anything. Title and header: `2.0.0-beta.4`.
Home: Preflight OK, AUTO → GPU, AI completed: 2. Russian text and Chinese
`课程` in the data path were readable.

Catalog: exactly two lectures, dates 2026-10-16, parts 3 and 1, both `Готово`,
ASR progress shown as an em dash, Raw present, pending list empty.
Courses/Inbox: worker stopped via Task Scheduler, test course enabled,
zero waiting and zero problems; no false missing-heartbeat error.
No clipping was observed in the inspected controls at the current desktop scale;
this is not a new all-DPI qualification.

Closed via Alt+F4. Subsequent process inventory found no processes belonging to
the disposable installation. GUI log was empty (0 bytes); no callback errors.
No additional product fix was needed. Screenshots were inspected in the tool
transcript; no unrelated desktop screenshots are committed.

## VIC-20 and limitations

Published fresh beta.4 Setup contains both updater error-UX paths. Its embedded
application payload includes `launcher/update_gui.py` and versioned GUI updates;
their bytes match the accepted source. The Setup project embeds that payload;
public Setup hash matches the accepted build. Existing targeted GUI/error tests
and earlier published-build evidence are reused, not repeated here.

**Legacy boundary:** a code-only upgrade from v1.9.7-beta.2 does not replace its
stable `launcher/update_gui.py`; its old verbose staged-health error presentation
remains. No launcher migration is claimed or added. Fresh v2 Setup has the fix.

Qualification is for the current Windows 11 x64 / RTX 3050 host. Manual AI content
is a synthetic acceptance fixture. Explicit Integrate remains the current worker
registration step. No new beta.4 cold install was performed, as authorized.

## Safety and evidence

Five representative production/baseline control files retained SHA/mtime;
ten unrelated scheduled-task XML definitions remained unchanged. No operations
targeted working Beta, university/study or real Drive course data during beta.4
acceptance/closeout. This is scoped evidence, not a claim of a full historical
filesystem audit (earlier manual beta.2 folder-selection history remains noted).

Local detailed evidence: `.local/vic24/beta4/` — `assets.json`,
`public-verification.txt`, `update-apply.log`, `final-native.json`,
`user-before-update.json`, `post-restart-diff.json`, `integrate-apply.log`,
`final-update-check.log`, `protected-files.json`, `protected-tasks.json`, and
targeted test logs. Earlier ASR/manual-AI evidence remains under beta3.
This report and the sanitized asset inventory are durable repository evidence.

No release modification, version bump, beta.5, VIC-15 or new roadmap work.
