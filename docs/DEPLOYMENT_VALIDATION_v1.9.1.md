# v1.9.1 deployment-validation record

Status: **local candidate, NOT approved for public beta**. Clean OS logon/reboot and full native binary redistribution clearance remain open. No remote was created.

Environment: Windows 11 Pro x64 standard-user session. Sandbox executable, Hyper-V management and a configured VM were unavailable. A separate disposable installation was extracted from the v1.9 ZIP, with an external Unicode data root and empty profile/cache/Python environment for initial probes. Real tasks ran under the current user's session. OS-wide VC libraries/drivers and the real user logon session remain shared with the host: this is not a clean Windows VM.

Package-only rule: application/runtime came from the release ZIP; model and CUDA used only the explicit verified import flows. Missing application files were not supplied from production, system Python, Codex or Git. Rebuilt fixes were tested from rebuilt ZIPs. Git source was used only for development/build and targeted tests.

Observed fixes:
1. Missing document runtime previously created partial workspace/state before failing. Setup now probes ASR/document native imports before writes and emits an actionable prerequisite message. Regression reproduces absence and DLL errors without data creation. Read-only data root fails without a config or child files; a normal retry succeeds after prerequisites are restored.
2. Integration invoked Python without UTF-8, so a Chinese data root failed under a legacy code page. Initial UTF-8 test environment masked it; reinstall exposed it. Explicit `-X utf8` plus UTF-8 console output removes the ambient dependency. A real integration-plan regression clears inherited encoding settings.
3. Artifact naming preserves the full dotted version. Notices are included as manifest-owned files and the uninstall ownership list recognizes them. No backend/schema/ASR/dictionary/Word change.

Evidence includes: model absence; no CUDA => CPU fallback warning; unavailable data; invalid workspace; real user-scope task/shortcut creation; GUI close/reopen without stopping workers; task restart; one short Lecture and one short Dialogue through scheduled workers; output/idempotency hashes; actual manifest-owned uninstall and retained-data hashes; same-package reinstall with setup refusing overwrite; release ZIP/checksum verification. No H3 crash matrix or long ASR benchmark.

Audio fixture: locally synthesized 10.2456-second speech. Lecture explicit en: GPU int8_float16/VAD, process wall 19.969 s. Dialogue auto: GPU int8_float16/VAD, process wall 14.344 s, detected ru from the installed TTS voice. Functional deployment test, not an ASR quality benchmark. Lecture reaches completed and publishes TXT/SRT/manifest; external manual Word-AI processing was not invented.

VBS: removing the candidate VBS entry still allowed the generated `.lnk` to launch pythonw. WSH global policy was not changed. Real policy disabling the WScript.Shell COM class remains a managed-host limitation.

Login/reboot: **NOT TESTED**. No production-host logoff/reboot was performed. Enabled logon triggers and manual starts are not equivalent to a proven new-session launch.

Licenses: 102 texts and 221 native binary identities recorded; package-level and native-library terms are distinguished. Public distribution blocked pending exact FFmpeg/external-codec sources/build recipe/licensing reconciliation and remaining native transitive obligations. Model/CUDA are excluded from ZIP; no driver or VC redistributable installed. See THIRD_PARTY_NOTICES and PREREQUISITES.

Beta decision remains NO regardless of successful local functional checks. Next work is limited to obtaining the missing independent Windows login/reboot evidence and resolving redistribution prerequisites. No updater, GUI redesign, statistics, automatic remote push or beta release is authorized.
