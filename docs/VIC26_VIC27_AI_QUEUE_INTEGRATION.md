# VIC-26/27 + AI Queue Refresh integration gate (DEV, 2026-10-20)

Branch: `dev/vic26-vic27-ai-queue-integration`. Base: local `main`
`c256ae3beee5c014478a833c1d156e14d0b32a8c`. The branch contains the
VIC-26/27 code commits `4cdfa8a` and `45170637d7c64f4636acf19b6ace5c6e517db046`,
then a cherry-pick of AI Queue Refresh `af1832bd9ace95bccfdd9272ea4e24dabdb87b40`
as `abed196`. The stabilization branch also has a later report-only commit
`4ea8bd1`; it was left on its original branch. No VIC-30 or Work S GUI commit
is included.

## Verification

- General regression: 369 tests discovered; 367 passed, 2 skipped, 0 failed or
  errored. The two skips require a separate embedded Python smoke fixture and
  a disposable configured package. Thirteen Python 3.11 ABI tests passed within
  that total. `test_packaging` was excluded because this integration gate did
  not create an installed release layout. Evidence:
  `C:\PipLine GPT WORK\scratch\ai-queue-integration-temp\LP-vic23-tests-ks20ejcv\evidence.json`.
- Separate worker/AI queue gate: 10/10 tests passed. It covers visibility of
  `waiting_ai` before the next lecture's ASR, duplicate READY/restart, interrupted
  Raw publication, failed `state.json` commit, queue lock contention, lost spool,
  external Raw recovery, AI result recovery, and corrupt completed Raw detection.
  Fault tests assert the committed state and Raw/SRT bytes remain intact and no
  second ASR occurs. Evidence:
  `C:\PipLine GPT WORK\scratch\ai-queue-integration-temp\worker-ai-queue-gate.json`.
- Realistic queue refresh benchmark used only a copy of the frozen seven-part
  Methods Raw/SRT (699,645 bytes). First indexing took 0.483 s; five replay
  calls took 0.096–0.107 s. On ten disposable copies (6.93 MB), cold indexing
  took 4.084 s; three replay calls took 1.108–1.241 s. The gate limits were
  2 s for one lecture and 5 s for ten. Queue bytes were unchanged on replay;
  state, AI ledger, dictionary marker and Raw/SRT source hashes remained
  unchanged. Evidence:
  `C:\PipLine GPT WORK\scratch\ai-queue-integration-temp\methods-gate\evidence.json`
  and `C:\PipLine GPT WORK\scratch\ai-queue-integration-temp\methods-gate-10\evidence.json`.

The benchmark measures indexing after a Raw commit, not transcription speed.
The ten-lecture scenario duplicates one frozen lecture to test queue size; it
is not ten independent lecture recordings. Queue refresh scans all completed
manifests, so larger production queues could take longer. No excessive delay
was observed at the tested scale; measure again during the combined candidate
gate if the target queue is substantially larger.

## Integration boundary

The branch changes only worker queue timing, VIC-26 worker confirmation,
VIC-27 course setup, tests and documentation. AI queue locking, Word and
dictionary merge code remain unchanged. No Task Scheduler task was registered
for this gate, and no long GPU ASR was run. Production installations, Google
Drive, the working dictionary, GitHub `main`, release/tag/assets and the Work S
worktree were not changed.

Decision: ready to assemble and test a disposable common candidate after Work S
delivers VIC-28. The combined native GUI/worker/updater gate remains to be done;
this branch is not a release or a merge approval.
