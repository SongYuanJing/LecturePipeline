# VIC-13 Unified Lecture Catalog

## Pre-implementation authority audit (2026-10-11)

Base: `877044e`, `feature/course-setup-gui`. Catalog is a read-only projection,
not a ledger. No persistent cache is planned: rebuild by reading existing records.

| Fact | Authority | Projection rule |
|---|---|---|
| Course/name/paths | active workspace subjects/config, Config.subjects mappings | Current display name; identity workspace/course/key |
| Unreserved work | inbox.json sources/groups | Separate pending rows; group owns its members; no synthetic lecture key |
| Reserved identity | inbox lecture_key or manual handoff receipt | Join to the same course/key entity before READY |
| Audio/order/READY | sealed READY files/intake; managed audio | Preserve sealed file/member order, never infer a new identity from audio alone |
| Date | VIC-11 metadata in raw/READY/reservation/state | Published metadata first; legacy key fallback only through lecture_dates.metadata; no mtime/import-time inference |
| ASR | worker_jobs phase, worker_status observations, lecture state | Completed raw supersedes stale processing; explicit errors/review remain visible |
| Raw | raw manifest + completion record | Require referenced TXT/SRT presence; expose missing record or output; do not hash audio on refresh |
| AI | queue tasks, packet task identity, accepted result reference, ai_state.processed | Queue is read, never refresh()/bundle()/transition(); packet alone is not completion |
| Word | ai_state completion + final output/report | Existing Word alone is not Done; multiple completions are ambiguous |
| Vocabulary | ai_state vocabulary_status, finalizer receipt/dictionary linkage | Show merged/batch_pending/legacy; do not open or merge workbook on refresh |
| Recovery/problem | inbox review, worker/queue error, VIC-12 recovery_action | Show reasons; never acknowledge or repair |

Existing GUI adapter only unions queue/state/worker heartbeat keys; it misses
reservations, READY-only lectures and unreserved groups. Its AI-tab actions must
remain intact. A dedicated catalog replaces the Lectures tab only, loading in the
existing background snapshot thread. It never calls processing/recovery functions.

## Projection and precedence contract

One entity per `(active_workspace, course_id, lecture_key)`; stages are fields.
Pending identity is the existing group/source ID. No global deduplication.

Resolver order: known inconsistency -> explicit review/error -> proven recorded
final completion -> Word/vocabulary pending -> accepted AI result/building ->
raw committed / waiting AI -> uncommitted ASR job -> READY -> reserved/waiting.
Committed raw suppresses stale ASR activity. Unknown states remain review, not Done.
Final completion requires AI ledger plus available raw/Word evidence, not file
existence alone. Cheap structural/presence checks do not claim fresh SHA validation;
VIC-12 remains responsible for integrity validation and repair. Cross-file reads
are not one atomic snapshot; a concurrent transition may temporarily show review.

No cache, migration, write-on-read, ETA, processing percentages, destructive actions,
worker controls or new review editor. Existing Course/Inbox review is linked.

## Implementation

`lecture_catalog.build(Config)` returns workspace, items, pending and read errors.
Each item contains course identity/current name, immutable lecture key, VIC-11 date
fields, ordered members/count, resolved status/label, individual stage states,
output paths, known problems, recovery reasons and integrity-check limitations.
The projection includes disabled configured courses without enabling their workers;
`Config.subjects(include_disabled=True)` is an optional read parameter, not a config
schema change. Defaults and all processing callers remain unchanged.

The Lectures tab is replaced by CatalogPanel: course/status filters, ascending or
descending dates (unknown last), horizontally/vertically scrollable table, scrollable
details, four safe open actions, and a separate pending table. Pending selection links
to the existing CoursePanel record/editor; no duplicate review mutation logic.
Catalog refresh uses the existing background GUI snapshot thread. Damaged older
dashboard data no longer prevents the independent catalog from being displayed.
Other GUI tabs/processing actions remain in place. Existing safe_open now also allows
configured source roots, with unchanged existence/type and containment guards.

Resolver labels/order are centralized in lecture_catalog.py. Recorded final completion
requires raw completion plus AI ledger, Word presence and merged vocabulary status.
An old missing vocabulary state is explicitly legacy/review. Known report/completion
hash disagreement is a problem without reading/hashing the Word itself. A stale
transcribing job cannot override committed output; a known VIC-12 requires_review
observation remains visible. Raw without completion is exposed for VIC-12 recovery,
never repaired. Orphan Word is a problem, never Done. Unknown journal states and
ambiguous AI completions are problems. Unknown extra fields are tolerated.

## Acceptance checkpoint (2026-10-11)

**VIC-13 Done: final native visual/OS-open gate passed on Windows at 192 DPI.**

- 168 affected regression tests passed in 61.607 s, plus one added legacy fallback
  test passed in 0.099 s. One new GUI regression brings the total to 170 distinct
  passing tests, including 31 catalog cases. After the GUI fix, the new regression
  and four DPI tests passed again (5 tests, 0.756 s).
- Covers Inbox, multipart, Course GUI/DPI, dates, dedup/recovery, manual import,
  worker, AI/finalizer, pipeline and legacy/split output mapping.
- 300 synthetic READY entities: 3.003 s build on this host. Grouping uses indexed
  identities; no pairwise lecture scan or repeated media hashing.
- Rebuild with a fresh Config produces semantically identical output. No persistent
  cache exists to delete. SHA-256/mtime of config/data and journal bytes/mtime remain
  unchanged across projection/GUI refresh. No cache or ledger is created by reads.
- Read-only projection of an actual completed VIC-12 disposable finalizer bundle:
  Done, no problems (no processing repeated).
- `scripts/vic13_catalog_gate.py` creates three courses with Russian/Chinese names,
  eight lectures (one eight-part, five completed, AI pending, raw ready, missing Word)
  and one unresolved group missing part 2. Actual DOCX fixtures are openable; state
  records are synthetic. Task Scheduler/preflight are substituted; no ASR/network.
- Final interactive evidence: `%TEMP%/LP-vic13-gui-tds6_264/evidence.json` PASS,
  192 DPI, filters, row/details, horizontal scrolling at reduced width, resize,
  exact existing Inbox selection, safe-open validation, no state mutation and
  rebuild equivalence. Eight-row refresh: 0.021740 s.
- An initial harness assumed horizontal overflow at full width; all columns fit.
  The check was corrected to shrink the window first. A fixture Inbox schema was
  corrected and review-link assertion strengthened to check the actual group selection.

After desktop unlock, the corrected fixture was inspected through actual Windows
input at 200% (192 DPI). Russian and Chinese glyphs, headers, buttons, pending
reason, course filtering, eight-part selection/details and vertical scrolling were
readable. Horizontal scrolling was visually exercised after widening a column;
rightmost AI/Word headers remained reachable. Normal and maximized layouts were
inspected; reduced-width geometry/visibility was also asserted by the native gate.

The inspection found one small GUI defect: unchanged background refresh replayed
table-selection events and could replace selected lecture details with pending
details. Commit `d4e8635` skips unchanged catalog rendering; the regression verifies
detail text, scroll position and selection retention. No architecture change.

All four catalog buttons delegated to real `os.startfile`: DOCX, Raw folder, result
folder and source folder. `windows-open.json` records exact disposable targets.
Word opened a `lecture` document window (its page content was not visually reviewed).
Raw TXT was additionally opened through Explorer in Notepad: Chinese text rendered
correctly; the test tab was closed without edits. Result/source Explorer breadcrumbs
matched the fixture paths. Missing paths, an existing outside TXT and an invalid
inside EXE were rejected without dispatch.

After closing the test GUI, the process exited 0: data/config SHA-256 and mtime,
worker/queue bytes and mtime, and rebuilt catalog semantics remained unchanged.
No Tk callback errors occurred. The repo evidence file preserves the final results;
earlier locked/interrupted attempts are superseded by this completed gate.

## Limits / safety

Active workspace catalog only (existing workspace switch selects others). Legacy
unknown facts stay unknown. Completion means recorded pipeline completion with cheap
presence/contract checks, not a new deep integrity certification: no recurring audio,
Word or workbook hashes; dictionary state is ledger linkage, not workbook rescanning.
Concurrent atomic journal transitions can temporarily show inconsistent observations;
refresh never repairs them. No cross-machine locking or new processing promises.

Production, baseline, working Beta, university/real study data and releases/tags are
untouched. New writes are confined to repository and disposable Temp fixtures.
No version bump, push, release, updater change or VIC-14 work.
