# VIC-12 recovery audit and acceptance

Audit before code changes, 2026-10-11. Base: `2fed2a9`, branch
`feature/course-setup-gui`. The following audit was recorded before implementation;
final contracts and acceptance results follow below.

## Existing authorities and crash matrix

Source generation = workspace/course/path/size/mtime_ns; group = course/source
folder/normalized stem; lecture = reserved course/key; content = ordered sealed
member SHA-256 values. These are distinct. No global content identity.

| Point | Durable authority / artifacts | Existing restart action / gap |
|---|---|---|
| A discovery | atomic inbox.json source generation | Fresh stability observations |
| B stable | only in-memory timer | Repeat stability, no acknowledgment lost |
| C reservation | lecture_key in inbox.json, before copy | Same key reused; changed generation needs explicit review |
| D mid-copy | owned .ingest-UUID files, no READY | Rebuild owned copies; no original deletion; multipart never half sealed |
| E copy before seal | managed complete members, reservation | Check matching bytes and reuse same destination/key |
| F READY before ack | atomic READY with member hashes/intake | Validate same lineage and hashes, acknowledge; no recopy |
| G ack before worker | READY + inbox queued | Worker discovers independently |
| H processing before ASR | worker_jobs transcribing + token | Safe ASR retry |
| I during ASR | local staging, no publish plan | Safe ASR retry; not completed |
| J raw before manifest | spool files, no complete plan | Safe retry before durable commit; complete manifest needs recovery support |
| K raw committed before AI | publish.json + spool/raw, then external state | Existing publishing replay; gap if plan committed before phase change |
| L AI packet before queue | deterministic identity+input-hash packet directory | Existing verified packet reused by refresh |
| M AI result before queue | deterministic validated result JSON | Explicit accept retry; automatic recovery needs input-hash validation |
| N Word build | private .ai-v15-UUID staging, prepared packet | Retry building; partial folder is not final |
| O Word rename before state | complete output dir + processing report hashes | Existing finalizer validates and resumes state/dictionary commits |
| P final completion before heartbeat | ai_state, dictionary ledger, queue completed | Existing idempotent finalizer; refresh currently skips validation of completed artifacts |

Existing journals use the VIC-10 atomic writer (unique temporary file, fsync,
bounded Windows sharing retries). Pipeline save_state has its own older writer;
reuse the hardened writer rather than add another implementation. READY sealing
uses save_state. Word uses a complete staging directory rename, then H3 state
and dictionary transactions. AI packet uses a deterministic final directory and
hash list. Worker uses immutable spool publish plan, copies each external output
via pending/replace, and writes completed state after all output files.

## Scoped changes justified by audit

- Same-course content-equivalent new path/session: explicit review, not silent
  dedup or new lecture. No cross-course dedup. Hash at stable handoff, reuse READY
  hashes, not every discovery poll. Changed accepted lineage remains review.
- Recover publish plan even when its phase acknowledgment was lost. New raw
  manifests carry output hashes and sealed READY evidence so committed output
  can be proved; legacy missing evidence requires review rather than guessing.
- Completed state must validate required outputs; corruption is visible and does
  not cause automatic destructive regeneration.
- Recover a uniquely validated AI result after lost acknowledgment; keep stable
  existing AI identity. Validate completed artifacts on observation.
- Preserve existing finalizer/H3 recovery; prove real process termination at
  relevant boundaries instead of shipping runtime failpoint switches.

Missing/corrupt authoritative journals are not reconstructed speculatively.
Crash with durable authorities intact is the supported boundary; source cleanup,
forensic recovery, real reboot, releases and further roadmap phases are excluded.

## Implemented contracts

Schema 1 remains readable; all new evidence fields are additive. Source generation,
group and course/lecture keys retain their existing definitions. Content equivalence
compares member SHA-256 multisets within one course at handoff, not across courses.
A renamed/copied identical source with a new lineage requires review. Changed
accepted/reserved source generations also require review; retry/date controls do not
bypass this decision. Unchanged lineage reuses its reserved key and sealed READY.

Manual handoff now persists `.manual-handoff-<identity>.json` in the existing managed
audio directory before copying. It retains the original date, signatures, hashes and
key under the existing ingest lock (plus manual handoff lock). This receipt reserves
identity; only READY commits the handoff. It is not a second queue or database.
Automatic handoff continues to use inbox.json. READY adds source_lineage evidence;
partial copies never seal a multipart lecture. Lost READY acknowledgment verifies
the existing members and returns the same key without recopying.

Raw manifests add output_hashes and sealed_ready; completion records add
raw_manifest_sha256. Outputs are published before the manifest. A durable spool
manifest reconstructs a lost publish plan; a plan overrides a lost phase acknowledgment.
Committed external raw can restore completed state, including after temporary spool
loss, without ASR. Missing/corrupt completed artifacts produce a review error instead
of regeneration. Legacy bundles retain structural validation; historical hashes are
not invented, and forward recovery without sufficient proof requires review.

The existing atomic JSON writer now also serves pipeline state/READY. AI packet IDs
remain deterministic. One validated result with matching inputs restores a lost queue
acknowledgment; ambiguous results fail closed. Completed AI tasks validate raw and
final output evidence. Word staging/rename and H3 state/dictionary transactions are
unchanged and were exercised across process termination.

## Acceptance results (2026-10-11)

Finalization reran all 123 relevant tests together: PASS in 66.831 s. Previously,
123 distinct relevant tests passed: a 120-test regression (50.002 s), then affected
suites after small fixes (50 tests / 26.064 s, 4 dedup tests / 1.678 s and 5 raw tests /
1.254 s). These reruns add three distinct cases, not 59 new tests. Coverage includes
dates, Inbox, multipart, course setup/GUI/DPI, human UX, worker, atomic journals,
local finalization and recovery. No installer/updater/GPU requalification was run.

[Machine-readable evidence](vic12-acceptance-evidence.json) records keys, hashes,
counts and process exits for 18 actual Windows child-process kills:

- Single/multipart reservation, multipart mid-copy and completed copy, single and
  multipart READY (C–G).
- During ASR, committed spool, committed publish plan and external raw (H–K).
- AI packet and accepted result (L–M).
- Word staging, final directory rename and final completion (N–P).
- Manual reservation, multipart mid-copy and READY using persisted manual receipts.

Every recovered case has one key, READY, raw bundle, AI job/packet/result/completion,
Word and completed state. Replay leaves sealed output hashes/mtimes unchanged.
Original source hashes/mtimes and config remain unchanged. Only the interrupted
uncommitted ASR case repeats computation; committed raw is reused.

Evidence roots: `%TEMP%/LP-vic12-qb7898ff` (first 12 cases) and
`%TEMP%/LP-vic12-r9i1gh8r` (remaining six). The first harness initially counted a
hidden uncommitted Word staging document as final; correcting that harness count and
rerunning the affected cases passed without changing the Word publication contract.
The collector revalidated all 18 cases against files on disk.

An isolated limited-user, on-demand Task Scheduler worker completed two start/stop
cycles; its uniquely named test task was unregistered afterward. Policy evidence at
`%TEMP%/LP-vic12-policy-xkls143j` confirms same-course copy/changed-generation review,
cross-course independence and two actual Tk CoursePanel reopenings at 200% scaling.
The changed-generation policy case intentionally edits its generated fixture only.

## Intentional limits and safety

This qualifies process-crash recovery with durable authorities intact, not physical
power loss, real reboot, distributed locking or a long Google Drive sync run. ASR and
AI content are fixtures; filesystem publication, child termination, Task Scheduler,
Tk widgets and Word/dictionary finalization are real. GUI reopening is widget/service
validation, not a new installed-GUI mouse automation gate. Discovery remains stat
based; it does not rehash every source on every poll. Missing/corrupt authoritative
journals and ambiguous reimports require review; no forensic rebuild or new reimport
UI was added. Hidden uncommitted staging files may remain; cleanup is outside scope.

All gate writes use newly created disposable Temp roots. Production, baseline,
working Beta, real study/Google Drive folders and published releases/tags were not
modified. No original user audio was deleted or moved. No version bump, push,
release or VIC-13 work is part of this change.
