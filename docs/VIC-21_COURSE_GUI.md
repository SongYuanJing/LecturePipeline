# VIC-21 — Course setup, folder provisioning and Inbox review GUI

Implemented and disposable Windows/Tk acceptance-tested on 2026-10-09.
No release, version or updater change. No production/cloud data migration.

## Audit and compatible folder contract

Phase 3a attached an optional `inbox` object to an existing schema-1 subject.
The stable subject code remains the course identity. Managed input audio and
worker/AI/state contracts stay under their existing internal roots. Previously
`output_folder` mapped raw/SRT to `raw` and Word to `word` below that root.

The additive binding now supports:

```json
{
  "enabled": true,
  "source_audio_folder": "D:\\University\\Course\\Inbox",
  "archive_audio_folder": "D:\\University\\Course\\Lectures\\Audio",
  "raw_output_folder": "D:\\University\\Course\\Lectures\\Raw",
  "final_output_folder": "D:\\University\\Course\\Lectures\\Final"
}
```

Both split output fields must be provided together. They take precedence over
legacy `output_folder`; with neither split field, the existing `raw/word` layout
and legacy notes-folder/open behavior remain unchanged. Loading a config never
migrates or writes it. Explicit GUI save records the user's chosen mapping.
No output files are copied, renamed or moved. Changing output roots for a course
that already owns audio/results/state is refused, as in Phase 3a.

## Folder setup and safety

The separate Course editor offers:

1. **Existing structure:** read-only detection of a complete generic preset or
   the known university-style Russian/Chinese reference. It lists proposed paths
   for confirmation. Multiple/missing matches fall back to manual mapping.
   Names are a UI detection helper, never a core identity rule.
2. **Create recommended:** preview `Inbox`, `Lectures/Audio`, `Lectures/Raw`,
   `Lectures/Final`, then confirm creation. Existing directories are accepted;
   missing ones are created. A file at any expected directory component fails
   before creation. No existing file is overwritten or deleted.
3. **Manual:** four ordinary Windows paths, with optional archive. Missing
   directories are refused rather than silently created in this mode.

Validation rejects relative paths, output/source nesting, overlaps between
bindings, installation/internal roots and service/state data. Read access is
checked by enumerating source. After explicit Save confirmation only, unique
zero-byte output probes check write access and are removed by scoped cleanup.
Detection/preview do not write to candidate user folders.

Saving uses the existing GUI Manager config transaction: preflight, stop workers,
recheck relocation under producer locks, atomic config publication, restore the
previous worker states, rollback on failure. No second config system is added.
Confirmed folder creation is deliberately not undone by deleting directories if
a later config/runtime check fails; a retry reuses them. Running worker behavior
and runtime preflight remain existing product contracts.

## GUI behavior

The **Курсы / Inbox** tab lists course names, enabled status, pending session/file
count, local last-scan time and problem count. New courses get an internal
generated stable ID; rename and safe rebind retain it. The existing Workspace
"add subject" action also opens the new editor instead of requesting a code.

The lower table projects the existing intake source/group state with Russian
labels, found part numbers and reasons. Member rows are represented by their
group; late/unmatched sources remain visible. Group statuses still come from
existing worker/ASR/AI ledgers. The panel distinguishes enabled configuration
from a running worker and links to the existing worker restart action.

The editor is vertically scrollable, with fixed Save/Cancel controls. The status
panel reserves its bottom actions independently of resizable/scrollable tables.
No general application redesign, catalog or background updater is included.

## Explicit review actions

- **Date:** writes `lecture_date` and `lecture_date_source = explicit` without
  changing `imported_at` or using filesystem times. Group override updates its
  currently known members; it never merges differently named sessions.
- **Expected parts:** optional `groups[*].expected_parts` in existing intake
  state; Auto is null. A known count requires exactly `1..N`. It uses the same
  grouping/completeness engine and can be set while waiting or in review.
- **Check again:** clears the retriable intake error and requests fresh stability
  observations. It does not bypass missing parts, date conflicts or byte checks.

These changes are serialized by the existing Inbox producer lock. Published
groups and their late sources cannot be edited/requeued through this action.
After reservation, only retry of the unchanged handoff is allowed; changing date
or expected composition is refused. Unknown-date and gap reasons stay visible.
Complex merge/split and processing-stage retries remain outside this iteration.

## Verification and exact native scope

107 distinct targeted tests passed: previous 84 Inbox/multipart/manual/pipeline/
worker/finalizer tests, 15 course-contract tests, 4 real Tk widget/callback tests,
and 4 DPI tests. An initial combined run passed 102; following focused additions
and compatibility adjustments, 48 affected tests and the new permanent-failure
retry test passed. There are no unresolved test failures.

Finalization resumed on 2026-10-10 from clean implementation HEAD `674163d`.
Only documentation/evidence were pending; implementation was preserved.
The complete 107-test targeted/regression suite was rerun once: **107 passed
in 43.852 seconds**. Existing native evidence and the 192-DPI footer fix were
rechecked; the expensive native scenario was not repeated. The fixture's Course
panel differs from the final panel only in the already-tested human-readable
part-detail text. No protected installation/cloud paths were used for writes.

The final disposable GUI gate is:
`%TEMP%/LP-course-gui-20261009-213913`.
Evidence: `course-gui-native-2026-10-09.json`.

The native harness launches the real main Tk GUI, invokes real editor callbacks,
captures/accepts confirmation previews, creates physical Unicode folders, saves
through the real config transaction and recreates the GUI to check stable ID and
bindings. It then uses generated WAV files and real polling (minimum supported
10-second file/group settle; approximately 22.687 seconds for the recorded
multipart segment), checks queued multipart and unknown/gap review, worker input
acceptance, raw output in the selected directory, and actual fixture Word
finalization in the final directory. Existing-structure detection/confirmation,
manual editor rename/disable, restart duplicate prevention and retained originals
are covered.

**Qualification limits:** scheduler controls and runtime preflight are fixture
substitutes to avoid touching OS tasks or requiring a new runtime/model install.
The raw writer uses a stub recognizer, not Whisper inference. Word uses the real
existing fixture finalizer. Confirmation acceptance in the integration harness
is simulated; product confirmation dialogs remain enabled. This is native
GUI/filesystem/contract acceptance, not another installer or GPU qualification.

External Windows Computer Use inspected the main tab, Course editor and date
dialog at Tk 192 DPI (200%) on a 2880x1800 desktop. Unicode was readable.
The first inspection exposed status-footer clipping; the final layout keeps
actions visible, with geometry assertions in the harness. A long timestamp was
also shortened. Native text injection into the modal was unreliable, so actual
date/count Save callbacks were additionally exercised via real Tk entries and
buttons in `test_course_gui.py`, rather than claiming successful desktop typing.

## Deliberate boundaries

- Cloud drives are ordinary Windows paths. No Drive API/OAuth, fixed drive letter,
  sync completion guarantee, filesystem-date inference or actual cloud mount
  qualification. Tests use disposable Drive-like Unicode directory names.
- Archive remains a stored destination. The recommended preset may explicitly
  create its empty directory; no audio is moved after completion.
- Existing output relocation/migration and ambiguous group merge/split remain
  manual future work. Quiet-window limits persist unless the user declares an
  expected count before publication.
- No production/baseline/working Beta/real Drive folders, study data, updater,
  published release/tag or global Windows DPI setting was modified.
- Stop here. No VIC-10 or other roadmap phase is started automatically.
