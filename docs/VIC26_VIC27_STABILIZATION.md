# VIC-26 + VIC-27 stabilization (DEV)

Branch: `dev/vic26-vic27-stabilization`, created from GitHub `main` at `c256ae3beee5c014478a833c1d156e14d0b32a8c`. The separate VIC-30 branch remains at `c968b4f7b92cfa689f882b87e9f83bf81c933c2a`. Accepted `v2.0.0-beta.4`, production installations, lecture data, Drive and dictionary are unchanged.

Linear references: [VIC-26](https://linear.app/songyuanjing/issue/VIC-26/clean-install-course-save-can-stall-on-worker-restart-confirmation) and [VIC-27](https://linear.app/songyuanjing/issue/VIC-27/course-setup-can-silently-switch-user-onto-generic-inboxlectures). Both remained Backlog when read for this sprint. Their historical observations inform diagnosis; the initial worker crash/exit cause is still unproven.

## Established causes

- VIC-26: `WorkerControl.ps1` hands Start to Task Scheduler without waiting for a worker session. Registered tasks have a one-minute restart interval. GUI `confirm_started` used a 45-second deadline and recorded the Start request only after PowerShell returned. It also allowed a session started up to three seconds before the request, so an old session with a fresh heartbeat could pass. Timeout gave no Scheduler result or worker timestamp diagnosis. Linear records a later healthy worker and reproduces the failure on plain restart, independently of Course Setup.
- VIC-27: a new CourseEditor defaulted to creating generic `Inbox/Lectures` paths; that choice did not inspect existing university folders. `save_course` created both external and internal directories before entering `Manager.apply_config`, so failed transactions could leave the new generic tree behind. Preview text was static after path edits.

## DEV changes

- `Controls.action(Start)` records request time before launcher execution. Confirmation requires Scheduler Running and enabled, a `RUNNING` status with `started_at` after this request, and a heartbeat no more than 45 seconds old. The 150-second window covers the registered one-minute Scheduler retry and includes Scheduler state, last result, last run and worker timestamps on failure. A disabled task fails promptly. These observations distinguish a delayed launch from a stale status; they do not prove why the initial task instance exited.
- CourseEditor opens new courses in **connect existing structure** mode. Create recommended structure is an explicit separate choice; its confirmation warns about parallel `Inbox/Lectures`. Preview tracks path and mode edits, and changing the root after a proposal requires a new proposal before save.
- Course paths are checked without mutation before the config transaction. After workers stop and producer locks are acquired, only requested missing directories are created and tracked. The new config receives full preflight after those directories exist. If commit or worker confirmation fails and the old config is restored, only directories created by that attempt are removed, and only while empty. If worker rollback remains pending, these directories are retained for recovery. Existing folders and their contents are never deleted.

## Verification

- Worker confirmation: 10 fixture tests, covering immediate success, delayed Scheduler retry, delayed heartbeat, failed/disabled task diagnosis, old session rejection, Start timestamp race and config rollback. One test executes the PowerShell Scheduler snapshot using fixture functions, with no registered task access. The launcher Start path is also exercised with fixture Scheduler commands and an isolated stop marker.
- Course Setup: 20 tests, including pre-transaction directory absence, post-commit rollback, worker confirmation failure after folder creation, existing file preservation, and unchanged bindings after failed edit.
- Course GUI: 6 Tk tests, including default existing mode, live preview, stale root guard and explicit parallel-tree warning.
- Related regression: 7 Human UX, 4 GUI status, 2 worker control fixture tests and 3 targeted workspace/task identity tests. Total: **52 passing tests**.
- The disposable native Course GUI gate passed actual Tk callbacks, config transaction, existing-folder binding, fixture worker flow, Raw/Word paths and restart identity checks. Its evidence is saved under the DEV temporary gate folder. It intentionally leaves a window open for manual visual review; the DEV test process was closed after evidence was recorded.

## Remaining gate

No real Task Scheduler task was registered, stopped or restarted in this sprint. Native integration of an isolated task pair and real worker start/stop/restart is still required before a beta candidate; it needs separate authorization. The cause of the first failed Scheduler launch remains unproven; if startup still fails after the retry window, the new error includes diagnostic state instead of claiming recovery. A directory created by a failed save is deliberately retained if another actor has placed content inside it.

Decision: code is ready for controlled integration testing in a disposable installation. It is **not** ready to merge into `main` or publish as a beta without the native Scheduler/worker gate and review of that evidence.
