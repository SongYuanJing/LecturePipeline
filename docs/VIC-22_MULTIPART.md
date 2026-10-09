# VIC-22: automatic multipart Inbox

Implemented on 2026-10-09 over Phase 3a. No GUI, release, version, updater,
archive automation or processing schema change.

Subsequent Course GUI and explicit date/count review controls are documented in
[VIC-21](VIC-21_COURSE_GUI.md). They extend this baseline without replacing grouping.

## Architecture audit

Manual `human_ux.add_lecture` already accepts an ordered file list. It copies
parts to `<lecture_key>_1.ext`, `_2.ext`, etc., verifies copied bytes and publishes
one version-1 READY only after all files are present. READY records expected
count, names, sizes and SHA-256. `collect_lectures` sorts by numeric part index;
`read_ready` rejects missing, extra and duplicate indexes. Worker verifies input
snapshots and processes every part under one job/key. The existing ASR manifest
contains ordered outputs; AI/Word expects a review for each recording part.

Automatic grouping therefore only prepares an ordered list for this same
function. The sole automatic-specific single-source restriction was extended
to validate every member signature/path. No worker, ASR, AI or finalizer behavior
was replaced, and no second READY format or processing queue was introduced.

## Naming and identity

The existing `hints` parser supplies date/part hints and now session hints.
Strip only a recognized trailing part suffix (`_1`, `-2`, `part2`, `_part2`, etc.)
and its adjacent separator. Normalize the remaining stem with Unicode NFC,
case folding and outer whitespace trimming. Preserve all other stem content,
including the date. Course always comes from the watched folder binding.

Thus `微观2026_10_09_1` and `微观2026_10_09_2` share a stem;
`A-2026_10_09_1` and `B-2026_10_09_1` do not. Files without part hints retain
Phase 3a single-file behavior and do not enter a multipart candidate.

Group identity is SHA-256 of workspace ID, course ID, source folder and normalized
session stem. It remains stable while parts accumulate. The ordered member IDs
use Phase 3a path/size/mtime generation identity; adding or modifying a member
changes the candidate membership and restarts the group window. Neither identity
hash reads audio content. The existing import and worker integrity checks still
perform full byte hashing at handoff/verification.

A separate date-masked *family* is an ambiguity guard only. Pending candidates
with the same non-date stem but disagreeing date hints are held in review, not
merged or decided by majority. This catches `foo2026_10_09_1` together with
`foo2026_10_08_2`. Different non-date stems remain independent sessions.

## Stability and completeness

Every member first satisfies Phase 3a size/mtime observations and readable,
closed-writer checks. Then all members must remain stable through another
`settle_seconds` quiet window (default 120 seconds). Reuse the existing bounded
poll and settle settings; no additional configuration field or service.

New/changed members and open writers reset the group window. Restart resets
in-memory observations, never source/group identity. Previously known review
reasons remain visible while fresh observations are collected. New membership
returns to `waiting_parts`, then is re-evaluated after settling.

Only contiguous, unique indexes `1..N`, a known agreed lecture date and unchanged
membership allow handoff. Missing indexes, duplicates, conflicting/unknown dates
and disappearing known parts produce review with a reason. Status exposes
`groups` alongside the existing source/course view. Processing/completion is
still derived from the worker/ASR/AI ledgers, not authored by Inbox.

## Persistence and recovery

Schema-1 `inbox.json` gains an optional `groups` dictionary. Each group records
identity, stem, ordered member IDs, status, provenance and reserved lecture key.
READY's existing additive `intake` object records the group ID and ordered
`members` (source ID, original path, signature, part hint). Legacy journals load
without a migration; previously imported Phase 3a sources are never regrouped.

At handoff all source read handles deny writers, all signatures are rechecked,
and the common ingestion path is called once. The existing reservation callback
persists the key before publication. Number allocation includes persisted intake
reservations so another group/manual import cannot take a key after a failed
copy. A member-set change after reservation requires review rather than changing
an in-progress publication.

Lost acknowledgement uses the same Phase 3a READY replay: verify group identity,
ordered members and managed file hashes, then acknowledge without recopying.
Restart/repeated scans of queued groups do not call import again. Late or changed
parts of an already published stem require review; they neither mutate that
lecture nor become a second automatic lecture.

Source audio is retained. Output bindings and archive policy are unchanged.

## Tests and native gate

84 distinct targeted/regression tests passed: 18 multipart, 12 Phase 3a Inbox,
7 manual UX, 14 pipeline, and 33 worker/local finalizer. Injected failure logs
in worker tests are expected assertions, not failing tests. After the small
review-status persistence fix, all 18 multipart tests passed again.

New cases cover both requested naming styles, ordered Unicode parts, same-date
different stems, slow arrival, gaps (including subsequent recovery), duplicate
indexes, conflicting dates, single files, restart during/after accumulation,
lost READY acknowledgement, interrupted copy, changed reserved membership,
late/disappeared parts, open writers, reservation isolation and manual ordering.

`tests/native_multipart_gate.py` uses a fresh `%TEMP%/LP-multipart-<timestamp>`
on Windows 11, generated valid WAV/PCM files and real locks/files/READY. It checks
staggered arrival, a process restart during accumulation, a three-part lecture,
two other distinct same-date sessions, incomplete review (including after
restart), ordered worker input snapshots, unchanged managed SHA/mtime on rescan,
manual multipart order and retained originals. Evidence is in
`multipart-native-2026-10-09.json`. No Whisper inference is needed because the
processing contract is unchanged; this gate qualifies intake, not ASR quality.

## Intentional limits and next boundary

- Quiet time cannot prove that no future file will ever arrive. A lone `_1` can
  publish after both windows; a later `_2` becomes review, not a duplicate lecture.
- No explicit expected-count declaration or manual group resolver in this task.
- Date-masked ambiguity is deliberately conservative: simultaneous backlog from
  several dates with the same family may require review rather than guessing.
- Normalization does not translate arbitrary stem words or unify different date
  spellings. Session stems otherwise need to match; rename/copy reconciliation
  and global content dedup remain deferred.
- Already published Phase 3a parts and partially reserved legacy intake require
  manual review rather than automatic regrouping.
- Pending counts in course status still count source records, not lecture groups;
  consumers can inspect the additive group view for session counts.
- VIC-21 can build Course bindings and Inbox/group status UI over these contracts,
  including clear waiting/review explanations. It is not started here.

Production, baseline, working Beta, real study files and published releases/tags
were not used or modified. No push or release publication is part of this task.
