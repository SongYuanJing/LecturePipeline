# Sprint 10 — Native Reliability & Delivery Gate (DEV checkpoint)

Date: 2026-10-21. Branch: `dev/unified-dev-vic28`. Base commit: `154b078fb1bcadf777b6b3ff9ad32d745fd08b27`. All installs and test data below are inside `C:\PipLine GPT WORK`. Production, Google Drive, the working dictionary, GitHub main and published Releases were not changed.

## Regression result and diagnosis

The original unsplit document-runtime run is preserved in `unified-dev-build/sprint10/full-document-python.log`: 413 tests, 5 failures, 4 errors, 2 skips. The nine failures/errors had these causes:

| Group | Count | Cause and resolution |
| --- | ---: | --- |
| CTranslate2/component staging | 4 | Tests were invoked with document Python 3.12 instead of the ASR Python 3.11 fixture. The isolated ASR partition passed 13/13 under Python 3.11. |
| Multipart inbox | 2 | Test code decoded UTF-8 Chinese fixture paths with the Windows CP1251 default. Explicit UTF-8 reads corrected the fixture; the related module passed 20/20. |
| Packaging task names | 1 | A stale `LECTURE_CONFIG` environment variable overrode the test's disposable config. The test now scopes that variable. |
| Packaging ASR source baseline | 1 | The test referred to absent tag `v1.8.1`; it now checks the five unchanged ASR/source files against accepted main `c256ae3beee5c014478a833c1d156e14d0b32a8c`. |
| Packaging GPU fallback | 1 | The installed fixture selected CPU while the assertion expected Auto fallback. The fixture now selects Auto. |

The two original skips lacked the isolated Python 3.11 and deployment-root fixtures; both were supplied for the final split run. The final document-runtime run (`full-document-split-final.log`) passed **401/401 in 280.890 seconds**. Together with the ASR partition (13/13), the split regression passed **414/414, zero failures/errors/skips**. A separate related regression passed 112/112 in 28.983 seconds (`focused-regression.log`). The final full run was not repeated.

## VIC-33 native GUI and worker gate

`native-lifecycle-retry.json`: 20 WebView2 open/close cycles, five Tk cycles, second-launch single-instance behavior, forced WebView2 exit and recovery, port/PID/session release. Fourteen existing DEV data files retained their hashes; no DEV Scheduler task was created. The fresh side-by-side installation also passed two WebView2 and one Tk cycle (`initial-install/native-first-install.json`). The desktop host now holds an OS-backed single-instance lock before opening a loopback port and WebView2 profile; the duplicate-launch regression is in `test_vic28_dashboard.py`.

The first disposable worker experiment used a direct CLI invocation without `-X utf8` and failed when Windows CP1251 could not print Chinese ASR text. The existing launcher uses `-X utf8`; recovery of the same pending lecture with that flag completed and published Raw/SRT/manifest without duplicate queue entries (`worker-recovery-utf8.log`). A final fresh two-second fixture used `-X utf8` from the start: WebView2 closed while the worker status was `TRANSCRIBING`; the worker remained alive after GUI exit and then completed, publishing four Raw/SRT/manifest files. A repeated worker cycle left the state and files unchanged, and the AI queue contains `METHODS/03_2026-10-20` as `waiting_ai` (`worker-gui-success.log`). The wrapper's 90-second wait expired before the worker process exited, although the worker later completed successfully; the wrapper timeout is a **test-gate limitation**, not evidence that GUI closure interrupted ASR. Do not claim a bounded 90-second ASR completion from this fixture.

An OS sleep/resume gate was not run because the Production Lecture worker was active. The scheduled CUDA smoke was skipped to avoid competing for the Production GPU; the isolated CPU ASR check above succeeded.

## Delivery and update gate

The local code-only `dev.3 → dev.4` update passed fault-injected rollback and successful update on `unified-dev-build/sprint10/update-copy`; pointer rollback and data preservation were checked. The existing `unified-dev/app` installation was also updated to `2.0.0-beta.5-dev.4` after that copy gate; 14 data files, configuration and AI queue hashes were unchanged. This update path applies only to an already shell-capable DEV installation. The local update archive is `unified-dev-build/sprint10/dev4-update/LecturePipeline-app-2.0.0-beta.5-dev.4.zip` (SHA-256 `884e27436269c929dfb9208053e2b3ba709cadf08f1b635d7025b397c687dab5`).

The side-by-side portable `Setup.cmd` first refused an occupied data folder without overwriting its sentinel. A fresh isolated install then passed Setup and Preflight after importing verified local components/model. It was launched as a normal DEV app and passed the native GUI gate. The local portable archive is `unified-dev-build/sprint10/portable-dev4.zip` (84,250,655 bytes, SHA-256 `2cfdc9da12f6b61fc4f1bae3009eadb5019681b29772a729e8dba391d67bd68f`). It is a thin package and needs the separately verified local components; it is not a self-contained installer.

**Setup.exe remains unverified and is not ready for an existing beta.4 installation.** Its project requires .NET SDK 10.0.401, which is absent on this machine, so no Setup.exe was built or run. Its current install engine refuses a different version on occupied data, and its shortcut/launch path still selects Tk. The publish bootstrap also needs a shell-aware packaging path. A code-only updater cannot introduce the shell into beta.4. No beta.4 migration or public package was attempted.

## Checkpoint state and decision

The three DEV install roots (`unified-dev`, `update-copy`, `initial-install`) had zero running DEV processes, zero matching DEV Scheduler tasks and zero session lock files at checkpoint. No `.pending`, `.tmp` or `.partial` files remained in their `app/run` trees; the dedicated `unified-dev-build/tmp` folder was empty. Logs, disposable installs and archives were retained for inspection. Workspace use was approximately **24.57 GiB**, within the 50 GiB limit. The Production Lecture task remained `Running` and was not touched.

**GO** for user evaluation of the existing, isolated `C:\PipLine GPT WORK\unified-dev\app\Lecture Pipeline DEV.vbs` with its separate DEV data. The new dashboard is read-only; worker, AI and course controls still use the Tk fallback. **NO-GO** for replacing beta.4, installing this shell into existing user data, publishing a Release, or calling Setup.exe production-ready. Those delivery gaps are the next release gate, outside this checkpoint.
