# VIC-23 — integration checkpoint (pending final GUI reopen)

Status on 2026-10-13: **not Done; no push**. The user explicitly selected checks
without GUI control after stopping Computer Use with Escape. Do not turn prior
visual observations into a claim that the final reopen passed.

## Repository boundary

Starting branch `feature/course-setup-gui`, HEAD
`95c7aeb9547a667bd98beadd55eaf5d65e9eece8`; initially clean, no upstream.
Origin is `SongYuanJing/LecturePipeline`. Read-only `git ls-remote --heads origin`
returned `feature/bootstrap-downloads` at
`fe69c9bf1304537e4257d41f12fee1035816a60e` and `main` at
`47d73cfe1029ed44ac76e9751f6ae9d596758e34`. The new development branch was absent.
Refresh remote state again before any future push; do not force or merge main.

The starting checkpoint contains VIC-9/10/11/12/13/14/21/22. Required fixes are
ancestors: `cd13686` updater diagnostic UX, `800bea7` dated session families,
`3008e72` Windows atomic journals, `d4e8635` selected catalog details, `560f0fa`
progress. VIC-20 remains pending inclusion in an approved published build; this
development checkpoint is not that build. No release/tag/version change.

## Genuine integration fix

The combined suite exposed scroll-position sensitivity while replacing detail
text. `86e0945` settles Tk text layout before restoration. The follow-up preserves
the bottom explicitly when new progress text changes wrapping. The existing test
now checks the meaningful bottom/selection/table-scroll contract rather than an
obsolete fractional coordinate. No processing, data or updater contracts changed.

## Reproducible checks

From the repository, use a development Python with Tk/document test dependencies
and a separate CPython 3.11 x64 interpreter for pinned ABI fixture tests:

```powershell
& $TestPython -B -X utf8 scripts/vic23_combined_tests.py --python311 $Python311
& $TestPython -B -X utf8 scripts/vic23_integration_gate.py
& $TestPython -B -X utf8 scripts/vic23_integration_gate.py --drive
& $TestPython -B -X utf8 scripts/vic23_checkpoint_audit.py
```

The combined command creates a fresh Temp fixture and includes config, manual
intake, Courses/Inbox, multipart, dates, recovery, journals, worker/raw, AI/manual
packet, Word/vocabulary, catalog/progress, GUI/DPI and updater tests. ABI-specific
wheel tests run in its 3.11 child. Counts refer to distinct cases, not summed reruns.
`test_packaging` is excluded because it requires an installed release layout;
VIC-23 does not build a release. Two opt-in deployment/runtime smokes can skip when
their explicit environment roots are absent. Exact final totals are in the adjacent
`vic23-acceptance-evidence.json`.

Earlier harness attempts used the wrong ABI, a stale fixture config, an incorrect
child import path, or included GUI logs in authoritative invariance. Those attempts
are not passes. Injected failure tracebacks in console logs are expected negative
tests; the unittest result, not console keyword matching, determines success.

## Fresh integration and bounded Drive

Main evidence: `%TEMP%/LP-vic23-integration-vm101d7i/integration-evidence.json`.
Three RU/Chinese Courses: A single WAV, B parts 3/1/2 arriving out of order, C
incomplete parts 1/3. Real Course setup, stability scans, ordered handoff, date
resolution, reservation, two READY records, worker raw publication, validated
manual-compatible AI fixtures, two real Word documents and vocabulary finalization.
Catalog has two completed lectures and one review group; completed rows have no
live progress. Six source SHA-256/mtime pairs unchanged. Producer reconstruction
does not add READY; worker stop/start does not repeat four fixture ASR calls;
repeated finalization leaves Word/dictionary/AI state bytes and mtime unchanged.
Repeated catalog reads leave fixture files unchanged.

Because post-VIC-10 recovery changes touched reservation/handoff, a compact real
Drive filesystem run was justified. Evidence:
`%TEMP%/LP-vic23-integration-o5wg85eb/integration-evidence.json`, with the six tiny
synthetic sources and outputs confined to
`G:\Мой диск\test\LP-vic23-integration-o5wg85eb`. Same integration assertions PASS.
This is a mounted Drive filesystem test, not a new cloud sync/outage qualification.
Retain the prior VIC-10 evidence for actual upload/staggered arrival behavior.

ASR and Task Scheduler are explicit fixtures in these integration runs. Actual
large-v3/RTX 3050 qualification is reused from VIC-14 because its recognizer and
instrumentation path has not changed: `%TEMP%/LP-vic14-asr-lvs9ohcg/evidence.json`.
No model downloads or native ASR repetition.

## Native GUI evidence and remaining gap

On 2026-10-12 the real main GUI at 192 DPI/200% showed readable RU/Chinese labels,
Catalog and Course editor, multipart details, pending-to-Courses navigation,
normal/minimum-width and maximized layout, filters and horizontal scrolling.
Word opened through the actual GUI action and displayed the generated three-part
document; it was closed without edits. No callback errors. Authoritative config,
READY, journal, raw, AI/completion, Word and dictionary fingerprints did not change.
Exact report:
`%TEMP%/LP-vic23-integration-vm101d7i/gui-evidence-1791805060536097600.json`.
Only the application's GUI log is excluded from authoritative comparisons.

A fresh live progress fixture also passed widget checks and visual inspection:
`%TEMP%/LP-vic14-gui-8p47dvei/evidence.json`. Four rows, changing 3/8 progress with
ASR ETA, insufficient-data row without ETA, waiting/completed rows without progress;
vertical scrolling verified. No authoritative mutation or Tk errors. Scheduler and
progress observations here are simulated, not actual ASR timing measurements.

Final same-fixture GUI reopen was started but interrupted before inspection/close.
The subsequent bottom-scroll refinement has targeted/combined test coverage but
has not received a new native visual check. Both are pending until the user permits
GUI control again. Do not replay the expensive integration/ASR gates: repeat only
the affected GUI checks and confirm the final fingerprint report.

## Compatibility, hygiene and scope

Regression covers no-Inbox configs, legacy date provenance/unknown values, schema-1
raw/AI state, legacy output_folder and split Raw/Final, old worker observations with
no progress, and read-only catalog projection. No forced migration was added.
Safe-open containment/type/missing-path guards remain covered by regression.

Checkpoint audit scans every new blob since the remote development checkpoint and
working files for key/token/credential URL/personal-home patterns. No findings in
the scanned range; tracked runtime/audio/documents/screenshots/binaries were absent.
This is a bounded pattern scan plus review, not a claim to detect every possible
secret. Legitimate accepted evidence was retained. VIC-10 test paths refer only to
the explicitly approved Drive test folder; no university lecture text was added.

Production, baseline, working Beta, university folders and existing study data were
not used or modified. No cleanup, new feature, VIC-15, release, tag or global settings
change. GitHub push remains conditional on complete acceptance and clean state.
