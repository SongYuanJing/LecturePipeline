# Local AI finalize

The runtime boundary is: local ASR → one immutable waiting_ai packet → ordinary ChatGPT → ai_content.json → local finalizer. No Codex/Work, chat history, API, network or ASR call is required to finalize.

From the application directory, use its private document Python:

```
runtime\document\python.exe -B -X utf8 versions\1.9.4-local-finalize-candidate\ai_finalize.py --config config\config.json --task semester-1/SUBJECT/01_2026-09-28 --content "<external ai_content.json>"
```

The task must already exist and belong to the active workspace. No queue-wide refresh/scan or automatic lecture selection occurs. The external result must satisfy the existing AI content schema (schema_version 1), hashes, references and literal quote checks. An empty vocabulary list is valid. Invalid content is rejected before queue/output/state/dictionary writes. The finalizer does not repair or rewrite intellectual content.

Word output is `<configured subject ready/word directory>/<lecture key>/lecture.docx`, alongside ai_content.json, vocabulary_batch.json, source_packet.json, processing_report.json and ai_state_patch.json. Existing unrelated output directories are refused. The configured dictionary alone is merged, preserving manual fields and existing sense disambiguation rules.

## Identity compatibility

Legacy Drive prepare/commit remains supported, with all four real Drive IDs and its content/visual review receipt still required. Old ai_state records and dictionary source_file_id inputs remain accepted unchanged.

Local records have a distinct `source_key` (canonical file URI, never a fabricated Drive ID) and `provenance.kind=local`, workspace, raw/manifest canonical paths and SHA256. Subject/lecture identity and all raw/SRT/manifest hashes remain in the existing packet/report. Local ai_state entries use this URI as their processed-map key and have no mandatory source_file_id. Optional genuine Drive IDs may remain additional provenance. Local Word output path/hash and dictionary path/hash/transaction are recorded separately. Schema version stays 1: fields are additive; no existing records are migrated.

The hidden dictionary provenance column historically named source_file_id stores the selected source identity; for local inputs its value is the explicit file URI. Full source JSON preserves the distinction. The merge ledger uses this same identity and exact batch hash. Empty vocabulary writes only a ledger entry, allowing idempotent completion without invented terms.

## Validation and recovery

Local completion requires deterministic schema/reference checks and python-docx readability/required-section checks. This is recorded as structural validation, **not** as a human visual/content review. The external AI content remains available for human review. Legacy Drive visual-review requirements are unchanged.

The official controller uses existing queue accept/prepare/transition functions, Word builder/commit, dictionary merge, and unchanged atomic_publish/windows_publish. Each state/XLSX publication retains stable H3 locking, staging, fsync, semantic validation, guarded replacement and recovery. A separate per-task controller lock serializes finalizers on the same machine; this is not a cross-machine cloud lock.

The operation spans separate durable transactions, not one atomic transaction over Word, state and XLSX. Failure may leave built Word or a batch_pending ai_state record, but never marks the queue completed. Diagnostic and checkpoints live in `run/ai_queue/finalize/<task hash>/`. Rerun the same command with the same content to resume after resolving the reported issue. Changed source/content/output, ambiguous terms, missing transaction proof or unrelated concurrent dictionary changes fail closed; no automatic rollback overwrites external edits.

Successful repeated finalize verifies the output and dictionary ledger and returns completed without duplicate terms or reprocessing. It does not require the dictionary to remain byte-identical after later manual edits.
