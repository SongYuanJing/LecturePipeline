# AI Queue Refresh (DEV)

Baseline: `main` at `c256ae3beee5c014478a833c1d156e14d0b32a8c`.

## Cause and boundary

`lecture_worker.py` previously called `ai_queue.refresh` only after its entire
polling cycle. A second long lecture could therefore begin ASR while the first
lecture's committed Raw was still absent from the manual AI queue.

The worker now refreshes the queue after each successful Raw and `state.json`
commit, including the existing Raw recovery paths. The end-of-cycle refresh
remains for recovery after a transient queue failure or worker interruption.
Queue refresh keeps its existing `queue.lock`, source hashes, and idempotent
`persist` behavior. It does not finalize AI results or write to the dictionary.
A queue failure is logged and leaves the committed Raw and worker job intact.

## Verification boundary

Disposable worker tests cover visibility before the next ASR, repeated cycles,
queue lock contention, failed state commit, and recovery without a second ASR.
The AI finalization and recovery tests continue to cover dictionary and ledger
idempotency. No production worker or user data is used in these tests.

VIC-26/27 stabilization leaves `lecture_worker.py`, `ai_queue.py`, and
`tests/test_worker.py` identical to this branch's base commit. Its changed files
do not overlap this patch. A combined native build still needs its own gate.
