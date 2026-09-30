# Architecture / authoritative boundaries

The authoritative version pointer is application-root `current.json`. Stable `launcher/launch.py` validates the selected `versions/<version>/release.json` and code hashes, reads `config/config.json`, performs preflight, then invokes existing modules. Config `install_root` selects versioned code; additive `application_home` selects the outer mutable home. Legacy schema-1 config without the new field still means home = install root.

- **ASR:** `lecture_asr.py`, unchanged v1.3 child isolation, large-v3, cuda/int8_float16/beam5/VAD; CPU int8/no-VAD fallback. `Config.new_model()` supplies private HF cache and CUDA path.
- **Lecture:** `lecture_worker.py` / `lecture_pipeline.py`, existing READY/DONE/state semantics. Active workspace only. Controls use `Config.ps1`; candidate task names are per-installation.
- **Dictionary:** `dictionary_merge.py`, manual fields/provenance/merge unchanged. New first-run empty workbook uses the existing v1.4 schema, not a migration of user data.
- **Word AI:** `word_ai_v1.5/lecture_ai.py`, manual external ChatGPT and versioned instructions. Local packet/queue/state, never chat history, are authoritative.
- **Dialogue:** `dialogue_v1.6`, own state/journal; reused ASR and separate private document Python. No lecture READY, subjects or dictionary.
- **Config/workspaces:** schema 1, config describes external data/workspaces/subjects and component paths. Packaged root paths are relative; data root is explicit absolute user configuration.
- **GUI:** existing Tk app and adapter, controls/query modules only. GUI does not own worker lifetime or duplicate backend processing.
- **Atomic publish:** `atomic_publish.py` and `windows_publish.py` unchanged. Same-machine H3 guarantee only; no new cloud locking claims.

Code, release metadata, launcher and private Python are application-owned immutable files. Config, model cache, logs, local worker/queue state and backups live outside versions. Audio/raw/SRT/Word/XLSX and lecture/AI state are external user data. Never delete or migrate these implicitly on uninstall/update. Working state and integration belong to the installation; do not run two installations against the same data.

Future updates: tagged release -> verify authenticity/checksums -> stage version -> explicit reversible migration if required -> health check -> switch `current.json` and config code root as one guarded operation -> rollback on failure. No updater is implemented. A version pointer alone is insufficient: config/current mismatch fails closed. Never use a GitHub main branch as update feed.
