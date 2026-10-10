# VIC-10 Google Drive Desktop acceptance — PASS

Completed 2026-10-10, branch `feature/course-setup-gui`.
Evidence: `vic10-acceptance-evidence.json`; workbook:
`G:\Мой диск\test\VIC-10_acceptance.xlsx` (four sheets, 10 PASS / 0 FAIL).

## Actual scenario

User created the main course through the real GUI and committed config
transaction: `course-e83b245879a0`, Google Drive VIC-10 Test, zh, source
test/Audio, separate test/Raw and test/Final, no archive. Auxiliary Staggered
course `course-bd6a7390cc46` used existing save_course + Manager transaction,
not direct config editing.

Actual inventory superseded the older expected missing-part inventory:
18 readable M4A files, Windows attributes Normal, three complete sessions.

| Source family | Parts | Resulting lecture | Output |
|---|---|---|---|
| 3_2026_09_16 | 1–5 | 01_2026-09-16 | 5 SRT + TXT + Word |
| 3_2026_09_18 | 1–5 | 02_2026-09-18 | 5 SRT + TXT + Word |
| 3_2026_09_21 | 1–8 | 03_2026-09-21 | 8 SRT + TXT + Word |
| DriveTest_2026_10_10 | 1–4, staggered | 01_2026-10-10, auxiliary course | 4 SRT + TXT + Word |
| Gap_2026_10_10 | 1, 3 | No key; review for missing parts | No READY/output |

No date mixing, late split or duplicate. Four published lectures are worker
DONE and AI queue completed. Auxiliary outputs are under test/Staggered/Raw
and Final. lecture_date comes from filename, imported_at is separate,
recorded_at remains unknown; mtime was not used as recording date.

## Measured staggered timeline (UTC+8)

- 21:07:40.921: parts 1/2 created as valid 32,044-byte WAV files.
- 21:08:04.872: first Inbox discovery.
- 21:08:55.965: parts 3/4 appear, after 75.044 seconds.
- 21:09:10.933: monitor sees four parts, waiting_parts.
- 21:13:16.048: monitor sees one ordered queued handoff.
- Late parts to observed handoff: 260.083 seconds; total: 335.127 seconds.

Observations sampled every five seconds. Defaults unchanged: file stability
120 seconds, group quiet window 120 seconds, three observations, polling
30 seconds. Individual internal timer transition instants are not exposed.
This finite wait handled the measured pattern; arbitrarily late parts are not
guaranteed. Existing expected-part-count review remains available.

## Drive and restart evidence

Drive Desktop Home reported all files synchronized. History showed green
checks / «Файл загружен» for lecture.docx, packet/report/AI files and staggered
TXT/SRT. This is real sync UI observation, not inference from file existence.
Unicode mounted paths worked.

Existing controls restarted the real disposable scheduled worker. After
restart and scans, all five groups/member identities and keys were unchanged.
All 104 monitored source/output/READY files retained SHA-256, size and mtime;
original 18 M4A files also matched their initial baseline. Final heartbeat:
RUNNING at 21:24:27, all four lectures DONE. Disposable worker then stopped
normally; both disposable tasks are not running. No cleanup or source moving.

## Fixes and regression

- `800bea7158babd0048a72a5606f432a631ef3864`: date-family guard rejected
  repeated prefixes across independent dates. Regression reproduced zero READY
  instead of three. Overlapping part numbers now permit independent dated
  sessions; disjoint conflicting-date fragments still require review.
- `3008e72`: Windows readers briefly prevented journal replacement; worker
  heartbeat/main writes shared a staging name. Existing atomic writer now uses
  unique staging and six bounded attempts (620 ms total wait), only for Windows
  sharing/access-denied errors. Persistent failure preserves old journal and
  raises. Native restart repeated after installing this fix passed again.

99 distinct relevant tests passed: 76 Inbox/multipart/course/GUI/DPI/human UX/
local finalization, four journal tests, 19 worker tests. Combined 80-test run
initially passed 79: the concurrent test barrier failed when a Windows retry
re-entered after its peer finished. Test now synchronizes first attempt only.
All four journal + 19 worker tests then passed (23 tests, 4.054 seconds).
Real Windows tests cover an 80 ms reader lock, persistent denial, unrelated
errors and concurrent distinct staging. No unrelated expensive qualification.

## Limitations and safety

Whisper model/transcription and AI answer content were fixture-substituted.
Inbox, scheduler, config controls, READY, raw publication, Word finalizer,
filesystem and Drive were real. No new ASR quality/performance claim.

M4A inputs were already locally readable. Controlled arrivals were local writes
through Drive followed by real upload. Slow remote downloads, placeholders,
outages and open cloud writers were not natively simulated; relevant stability
cases are covered by regression.

Runtime/logs: `%TEMP%/LP-vic10-20261010`. Source baseline, observations.jsonl,
staggered-events.json, restart-evidence.json, test logs, workbook builder and
four visually inspected previews retained. Workbook is evidence, never app state.

No writes to university folders, production C:\WhisperLocal, baseline
C:\PipeLine, working Beta or study data outside test. Protected paths excluded,
not exhaustively rehashed. No release/tag, updater changes or next phase.
