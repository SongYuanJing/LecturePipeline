# Phase 3a: Local Lecture Inbox Core

Implemented and disposable Windows acceptance-tested on 2026-10-09. No release
or version change. GUI folder editor remains a separate iteration.

## Audit and integration decision

The existing GUI calls `human_ux.add_lecture`, which copies selected audio into
managed subject audio and seals a READY manifest. `lecture_worker` consumes that
manifest, verifies input snapshots, and uses its existing job journal and ASR
pipeline. Completed ASR state feeds the existing AI queue and Word/vocabulary
finalizer. Inbox is an additional producer at `add_lecture`, not another queue.

Existing subject code is the stable `course_id`, scoped to its workspace;
subject name is `display_name`. Changing a name or source folder does not rename
the course. No schema migration or new processing database is required.

## Additive contracts

Schema-1 subject objects may contain:

```json
"inbox": {
  "enabled": true,
  "source_audio_folder": "D:\\Lectures\\Micro\\Audio",
  "output_folder": "D:\\Lectures\\Micro\\Results",
  "archive_audio_folder": null,
  "poll_seconds": 10,
  "settle_seconds": 120,
  "stable_observations": 3
}
```

Absent bindings leave legacy behavior unchanged. Folders must be absolute and
non-overlapping, separate from installation, managed subjects and service data.
Raw output goes to `output_folder/raw`, Word to `output_folder/word`; managed
audio retains its existing location. The binding command refuses relocation of
a course that already has audio/results/state and requires an empty new output
folder. This iteration does not migrate existing output.

`worker_home/inbox.json` (schema 1) records source discovery, stability/handoff
state, reserved lecture key, course scan errors and last scan time. An initialized
marker prevents silently resetting a lost journal. Existing worker/ASR/AI ledgers
remain authoritative for processing and completion; `status` derives their
states and pending counts without creating another processing ledger.

READY and raw manifest carry an additive `intake` object. It includes
`course_id`, `lecture_date`, `lecture_date_source`, `imported_at`, nullable
`recorded_at`, and automatic source identity/signature/key. AI packet provenance
retains it. Manual import records explicit date provenance. Old READY and
manifests without intake remain supported.

## Discovery, stability and recovery

Only direct regular audio files in the bound folder are scanned. Filename words
and prefixes never select a course. Date hints support YYYY_MM_DD, YYYY-MM-DD
and YYYYMMDD; trailing `_1`, `_2`, `part2` etc. are optional part hints. Invalid
or missing dates stay null with `unknown` provenance and `review` status; they
are not silently replaced with import or filesystem dates. The parser supports
an explicit override; a date-review editor is not included.

Identity is SHA-256 of workspace, course, normalized resolved path, byte size
and nanosecond mtime, not a full-content digest. Scanning does not hash audio.
The existing copy/seal/worker path performs full integrity verification when
handing off. Unchanged sources are not re-imported after scans or restart;
renaming/copying or changing metadata represents a different generation.

Defaults require three observations spanning 120 seconds. Poll is bounded to
5–300 seconds, settle to 10–86400, observations to 2–20. Size/mtime changes
restart settling. A nonempty file must be readable and pass the existing
Windows deny-writer check before handoff. Restart requires fresh observations
for unfinished sources. The existing worker owns polling: scans can be delayed
by its normal interval and synchronous ASR work, so poll is a minimum interval.

The common ingestion lock reserves a lecture key before publishing. A committed
READY with matching source identity recovers a lost intake acknowledgement;
unfinished publication retains its key and checks any existing target bytes.
Source files are never moved/deleted. Archive bindings are stored only; even
their directories are not automatically created.

## Minimal wiring and operation

Use the installation's private Python and the code path selected by current.json.
First create/select a subject through the existing GUI. Stop that installation's
worker before changing its binding; the command refuses a held worker lock.

```text
<private-python> -B -X utf8 <code>/lecture_inbox.py --config <config.json> bind --course <subject_code> --source <audio-folder> --output <new-results-folder>
<private-python> -B -X utf8 <code>/lecture_inbox.py --config <config.json> status
```

Optional binding flags: `--archive`, `--disabled`, `--settle`, `--poll`.
Restart the existing lecture worker to begin automatic scanning. `scan` performs
one observation/diagnostic scan; separate short-lived scan processes do not
replace the long-lived worker's stability window. Configuration changes require
worker restart under the existing config contract. Status reports configured
course names/folders, enabled flag, pending count, last scan and source errors.

## Verification

66 distinct targeted tests passed: Inbox 12, manual human UX 7, worker and local
finalizer 33, pipeline 14. Coverage includes required filename/date cases,
changing/open files, restart, duplicate prevention, lost acknowledgement,
reserved-key retry, legacy config, output relocation refusal, manual ingestion,
and provenance reaching the ASR manifest/AI packet.

`tests/native_inbox_gate.py` ran on Windows in
`%TEMP%/LP-inbox-20261009-161523` in 36.219 seconds. Two Unicode course folders,
generated PCM audio, real file writing/locking, real import/READY verification
and a fresh process restart were used. Three sources queued exactly once, an
unknown-date source stayed in review, copying and paused-open-writer files were
not queued prematurely, manual import succeeded, original sources were retained,
and archives were untouched. See `phase3a-native-2026-10-09.json`.

The gate verifies native ingestion and existing worker input acceptance, not
fresh model inference or AI output quality. No production/baseline/working Beta,
real study files, updater architecture, published release or tag was changed.

## Intentional limits / next iteration

- One automatic file becomes one lecture; part hints are not multipart grouping.
- No recursive watching, global content dedup or rename/copy reconciliation.
- Metadata identity cannot detect replacement preserving both size and mtime.
- Unknown dates and permanent intake failures require manual review; originals
  remain available for manual import. There is no new retry/date-edit UI.
- No embedded timestamp extraction, Drive API, archive moves or output migration.
- Next iteration: a small Course binding/status GUI over these contracts, with
  explicit review/retry actions. Do not start date/dedup roadmaps automatically.
