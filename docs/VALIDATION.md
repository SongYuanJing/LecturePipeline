# Candidate verification — 2026-09-27

Performed only in an isolated application tree / disposable external data root. Stable production was a read-only reference.

- 86 fast tests passed: existing ASR/profile/fallback, pipeline, worker, Dialogue suites plus 22 packaging tests. The old historical-state fixture test uses four synthetic completed entries instead of copying private production state into Git.
- Config compatibility, relative application-home paths, external data separation, missing model, missing CUDA with CPU fallback warning, unavailable data, alternate profile environment, private Word/Excel roundtrip, code checksums, controlled task identities, first-run collision refusal, new empty dictionary merge/manual preservation, workspace switching and failed validation rollback passed.
- Uninstall tests removed only manifest-owned synthetic app files, preserved config/model/state/logs/backups/external data, rejected path traversal. No production uninstall or real scheduled-task registration.
- Own CPython 3.11.9 imports Tk/faster-whisper 1.2.1/CTranslate2 4.8.2; own CPython 3.12.14 generates Word/Excel with python-docx 1.2.0/openpyxl 3.1.5. Environment PYTHONHOME/PYTHONPATH and alternate USERPROFILE do not redirect runtime imports.
- GUI constructed through private pythonw and the stable launcher, title 1.9.0-candidate, GetConsoleWindow = 0; test closed it after startup. This is a startup test, not a new visual/functional GUI audit.
- Preflight all checks OK with imported model/CUDA. Task/shortcut plan refers to private pythonw and stable launcher; Windows integration intentionally not applied.
- Exactly one real short Dialogue smoke: 16.805 s audio, auto -> en, CUDA int8_float16 + VAD, model load 10.953 s, transcription 3.156 s, whole job 15.843 s. TXT/SRT/DOCX completed. Model/ASR profiles unchanged. No long Whisper or old lecture reprocessing.
- Protected production: 57 code/config/release files and 112 data files matched reference SHA256; no changes. Both production workers remained RUNNING.

No H3 re-audit: atomic publisher, Windows replacement, dictionary merge and ASR implementation match the baseline after Git newline normalization. Packaging cannot prove a clean machine has all native OS prerequisites: v1.9.1 must validate logon tasks, shortcut policy, VC/native dependencies, offline component provisioning, real uninstall and first-run errors on a disposable Windows VM/profile. Public license/signing review remains before distribution.
