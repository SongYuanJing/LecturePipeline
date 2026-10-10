# VIC-10 Google Drive Desktop acceptance — in progress

Date: 2026-10-10. Not Done; no native acceptance claim.

## Audit and reproduced defect

Started on `feature/course-setup-gui`, clean `30bb68366c08917ae5b6d7aa544817db7ad45352`.
The actual mounted test Audio folder contains 18 readable M4A files, all with
Windows attributes `Normal`: `3_2026_09_16_1..5`, `3_2026_09_18_1..5`,
`3_2026_09_21_1..8`. Thus all three current sessions are complete, unlike the
older expected inventory. Reading and hashing succeeded; this does not prove
cloud synchronization or mid-download behavior.

A regression using those exact filename patterns reproduced zero READY files
instead of three. The date-masked family guard incorrectly treated every reuse
of a course prefix on different dates as a conflict. The minimal fix permits
independent dated sessions whose part numbers overlap. Disjoint dated fragments
remain ambiguous and require review. No groups are merged and date provenance
is unchanged. Added coverage for complete 5/5/8 sessions, restart idempotency,
and the originally expected two incomplete sessions plus one complete session.

## Verification

- Before fix: new real-inventory filename regression failed, `0 != 3` READY.
- After fix: 62 tests passed (26.908 s): `test_lecture_inbox`,
  `test_inbox_multipart`, `test_course_setup`, `test_course_gui`, `test_gui_dpi`,
  `test_human_ux`.
- Standalone `test_worker`: 19 passed (4.396 s), with import-time config explicitly
  set to the disposable candidate. Expected injected error logs are test cases.
- Initial combined invocation could not import the standalone worker without
  a config; corrected invocation above passed. Sandbox Temp permissions also
  required the normal host execution context.

## Resume location and blocker

Internal runtime/evidence: `%TEMP%/LP-vic10-20261010`.
`source-before.json` contains the 18 source SHA-256/size/mtime baselines.
`regression.txt` and `worker-regression.txt` hold test output.
Config: `app/config.json`; application copy: `app/code`.
The private CPU runtime was copied into this disposable home. Its genuine
preflight passes. Model/document runtime are read-only references to an earlier
disposable Phase 1c installation, not working Beta or production.

Two isolated, on-demand Task Scheduler entries were registered:
`LP-442c3683bf7a-Lecture` and `LP-442c3683bf7a-Dialogue`, with no logon trigger.
They have not been started. The lecture wrapper substitutes only Whisper model
construction/transcription with one short Chinese segment. Real worker,
Inbox/READY/publication/config controls remain in use. Dialogue is not exercised.

The actual Course editor is open in `Lecture Pipeline · VIC-10 disposable`.
Computer-use can click it but two focused text-input attempts left the field
empty. The user has been asked to enter/confirm the course through the GUI.
No course binding has been written directly to config. Native GUI creation
therefore remains blocked, and the running candidate still uses the original
pre-fix code snapshot. Before the worker starts, update its `lecture_inbox.py`
from the reviewed repository and reopen the disposable GUI.

Created only requested output directories under the authorized Drive test root:
Raw, Final, Staggered/Audio, Staggered/Raw, Staggered/Final. Original Audio files
were not written or deleted. No course/university folders outside that root,
production, baseline, working Beta, releases or updater were modified.

## Still required

Real GUI course creation; automatic mixed-folder ingest with default stability
timings; normal worker restart/rescan; generated incomplete fixture and staggered
1/2 then 3/4 arrival; actual Raw and fixture-backed Word outputs; Drive Desktop
sync visibility; final source invariance check; four-sheet acceptance workbook
at the requested Drive root. No workbook or native PASS is claimed yet.
