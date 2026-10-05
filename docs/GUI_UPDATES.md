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
