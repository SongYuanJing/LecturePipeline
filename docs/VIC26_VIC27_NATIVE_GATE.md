# VIC-26 / VIC-27 native integration gate — 2026-10-20

Branch `dev/vic26-vic27-stabilization`, starting commit `4cdfa8ae32c658e8b2b82d5ebde33e4dd473540e`. All operations used `C:\PipLine GPT WORK\scratch\sprint07-native-20261020-190304`, task prefix `LP-95d2ae79f1ea`, and the patched source copied from this branch. The test installation had its own config, data, copied dictionary, code, and private ASR Python/components. Its model cache and document runtime were existing DEV components read-only. No audio or READY signals were present. Preflight passed. Workspace size after testing: 5.32 GiB, below the 50 GiB limit.

## Real Task Scheduler gate

- Before registration, the exact task prefix was absent. The two new task actions pointed to the disposable app's `pythonw.exe` and `gate_launcher.py`; both began Disabled. The DEV Dialogue task was never started.
- Start: Task Scheduler Running/enabled, worker RUNNING, new `started_at=2026-10-20T19:10:46+08:00`, and current heartbeat. Evidence: `start-evidence.json`.
- Stop then delayed Start: a controlled 55-second launcher delay produced a confirmed new session after 62.25 seconds, past the old 45-second window. Evidence: `delayed-start-evidence.json`.
- Failure: an injected first launcher exit code 73 left the manually started task Ready/enabled with LastTaskResult 73. It did not automatically retry within the 150-second confirmation window, despite `RestartOnFailure` settings. The original code timed out with Scheduler result, last run, and old status timestamps. The DEV launcher log identifies this injected cause; the cause of any historical Production first-attempt exit remains unknown.
- Fix: `confirm_started` now re-dispatches Start once when Scheduler is Ready, enabled, reports a nonzero failure result, and LastRunTime proves the failure belongs to the current Start request. It does not retry on stale results or loop after a second failure. The same injected failure then recovered and confirmed a new worker session in 14.17 seconds. Evidence: `revised-retry-evidence.json`.
- Explicit Manager Restart produced a different `started_at` and running task in 16.61 seconds. Evidence: `restart-evidence.json`.

## Native GUI gate

The actual Tk `App` and `CourseEditor` ran with real `Manager`, `Controls`, preflight and the DEV Scheduler task. Three editor confirmations were exercised through native widgets; confirmation answers and one write failure were supplied by the disposable test harness.

1. Connected an existing university-style folder structure. An existing user-file hash and mtime stayed unchanged.
2. Explicitly chose recommended folder creation. Preview caused no creation; confirmed save created the requested folders and restored the worker.
3. Injected failure at the live config write after requested folders had been created. The original config bytes and running worker were restored, the transaction journal closed, newly created empty directories were removed, and the existing user file stayed unchanged.

Evidence: `native-gui-evidence.json`. This is native Tk callback integration on the host, not manual visual/usability acceptance.

## Regression and cleanup

- 52 focused VIC-26/27 tests passed on the isolated gate config; 3 packaging tests passed on the standard DEV config. The initial combined 55-test invocation ran the packaging tests against the disposable config and produced two fixture-layout failures (model cache outside its expected app home and duplicated Inbox bindings during a workspace fixture). Both passed with their intended config; no product failure was found there.
- Two new DEV tasks were stopped and unregistered after exact action/working-directory/description ownership checks. No tasks with prefix `LP-95d2ae79f1ea` and no matching DEV worker process remained. Evidence: `cleanup-evidence.json`.
- Production task names and states matched the initial inventory after cleanup. No Production configuration, dictionary, Google Drive data, beta.4 release, or GitHub main changes were made.

Evidence files and test logs are retained in the disposable gate folder; no large components were downloaded. VIC-26/27 are ready for a common **test build** and integration rehearsal, subject to normal packaging and native acceptance of that candidate. This gate does not authorize merge to main or a release.
