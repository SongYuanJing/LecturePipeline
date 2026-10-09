# Manual GUI updates

The main window has explicit Check updates / Update controls. There is no
automatic background check. The GUI invokes the installed Phase 2a CLI for
discovery and displays current/new version or "Установлена последняя версия".

Update opens the stable launcher's `update_gui.py` progress window. Its transient
`run/update-ui-<token>.json` readiness receipt lets the main window close only
after the progress window is ready. A captured Windows process handle ensures
the initiating GUI has exited before calling the same engine `apply_tag` used by
the CLI. Existing session/worker locks still block updates; workers are not
silently stopped. The main GUI explains handoff; the progress window displays
download, verification, stage and first-launch status. It cannot be closed during
the engine transaction. Engine failure leaves/restores the old pointer and shows
an error with an Open application button. Engine success already starts the new
GUI; the progress window then closes. Result diagnostics live under logs only.

No second downloader, release resolver, pointer, recovery journal, data migration
or config field is introduced. The only engine refactoring exposes existing CLI
check/apply-by-tag operations as functions. The existing staged-health, atomic
switch, first-launch receipt and rollback remain authoritative.

New Setup is required to obtain this stable GUI handoff helper. Earlier Phase 2a
bases keep their CLI updater; a code update alone does not upgrade their launcher.
Support target is Windows 11 x64. Release artifacts remain unsigned.

Targeted tests cover GUI result states, failed handoff keeping the old GUI open,
waiting for parent exit before entering the engine, progress/error propagation,
and delegation to the existing apply engine. Existing updater/rollback tests
remain applicable. Real beta acceptance is recorded separately after publication.

## Published GUI acceptance — 2026-10-09

Passed on Windows 11 x64 / RTX 3050, system DPI 192 (200%). Evidence:
[gui-update-gate-2026-10-09.json](gui-update-gate-2026-10-09.json).

- [v1.9.7-beta.1](https://github.com/SongYuanJing/LecturePipeline/releases/tag/v1.9.7-beta.1),
  source `ecb4e15`: actual published Setup downloaded/verified and installed under
  `%TEMP%/LPgui-20261005/Программа 课程`, fresh data sibling `Данные 课程`.
  Setup SHA-256 `2c0da40d774c17ab13eb4ba0901bebc8d61beb7ede29f18d0c7b5439911c471b`,
  51,818,448 bytes. Installation previously completed in 338.172 seconds with
  real base download and verified supplier-cache reuse.
- Before publishing beta.2, an actual click on Check updates showed
  "Проверка...", then "Установлена последняя версия". Update stayed disabled.
- [v1.9.7-beta.2](https://github.com/SongYuanJing/LecturePipeline/releases/tag/v1.9.7-beta.2),
  source `78325d3`: version-only successor, no new features. Prepared ZIP contents
  were compared byte-for-byte with source and pinned runtime contract before
  publication. GitHub asset SHA/size matched local artifacts.
- Clicking Check updates in beta.1 showed both versions and enabled Update.
  Clicking Update showed the restart notice, acknowledged the progress-window
  handoff, closed the old GUI, downloaded the actual GitHub manifest/archive and
  ran the existing verified stage/health/atomic switch/first-launch engine.
- Actual new window: `Lecture Pipeline · 1.9.7-beta.2`. Installed diagnostic
  `logs/update-ui-result.json` confirms `updated` / beta.1 → beta.2.
  The pointer is `versions/1.9.7-beta.2`; beta.1 remains side-by-side and there is
  no pending transaction. Config, vocabulary and state SHA-256/mtime are identical.
- Final actual GUI click shows "Установлена последняя версия"; update-cache
  SHA/size/mtime are unchanged. No command files were used for GUI acceptance.

Beta.2 code ZIP: 103,725 bytes, SHA-256
`480ade7c081fe066f213b7598dddfa7906a69b21fa3ecea66daa68edafa5b921`.
Beta.2 Setup is also published: 51,818,450 bytes, SHA-256
`4d28f636749b784c29f716e56fe1f9933c6f633c05a03cee91d0ed3db1edbf7a`.
Its clean-install path was not repeated: this acceptance installs beta.1 and
updates to beta.2. Both are prereleases, not marked latest.

### Minimal UX review and separate fix

Buttons, checking state, current/new versions, restart notice and download
progress were visibly legible at 200% DPI, without clipping updater controls.
A saved real staged-health failure proved that raw Python traceback text could
reach the progress window. Commit `cd13686` keeps that diagnostic in the existing
log and shows a short failure message instead; check errors also use a short
message with details in gui.log. Seven targeted GUI tests passed, including the
saved native failure; a separate disposable native error-window fixture verified
the message and return/close buttons at 200%. This fixture does not claim a new
rollback test; rollback remains covered by the existing Phase 2a gates.

The text-only fix is **not in the immutable published beta.1/beta.2 artifacts**;
it is ready in source for the next approved build. No extra beta/tag was created
to expand this task. Happy-path GUI update qualification is complete; published
beta.2 still has the verbose staged-health error presentation limitation.

The existing main-page diagnostics for absent worker-status files remain visible
on this fresh installation where workers were not started. They are outside the
updater controls and were recorded, not redesigned here. There were no changes
to production, baseline, existing real study data or data/config contracts.
No background updates, migrations, cleanup or subsequent roadmap phase started.
