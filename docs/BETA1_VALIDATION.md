# Beta 1 validation scope

The accepted UX installation completed three audio parts → GPU large-v3 → combined raw + three SRT → waiting_ai → manual ChatGPT → GUI import → Word + vocabulary (+13) → completed. This acceptance was performed by the user. Source parity was verified for all 38 application/launcher Python and PowerShell files before release metadata/documentation changes.

Previously passed targeted suites are retained, not repeated. The release tail uses syntax/packaging sanity and one independent package-only installation with a short lecture reaching waiting_ai. No long Whisper benchmark, H3 audit, full ASR suite, repeated GUI automation or second ChatGPT/Word cycle is required because accepted application code is unchanged.

Detailed per-run results and artifact hashes are recorded outside the public source tree in the local release record. This is disposable-install validation on an existing Windows host, not clean-OS, reboot/login or legal recertification. Production and existing installations are not modified.

## Recorded result — 2026-09-30

PASS: final-code ZIP extracted into a new disposable application/data pair; CRC and all 7,231 manifest-owned file hashes verified. First-run window was mapped before any config existed; after documented imports/setup the main GUI reopened under private pythonw and closed via its normal callback. Tk instrumentation was used, no Computer Use. The earlier Windows process-window heuristic could not reliably close Tk and was replaced only in the test harness; application code was not changed.

Pinned PyAV, CTranslate2, model and optional CUDA imports passed. Setup created a fresh workspace/subject/config/dictionary; preflight returned all checks OK. Private Python import paths and isolated=1 confirmed package-only dependencies; components/model/CUDA were copied through the official importers, not borrowed at execution time. The host's Windows/VC/NVIDIA dependencies remain shared.

Two real unique Scheduled Tasks and a pythonw shortcut were created, with paths exclusively in the new installation. Both workers ran. A 10.2456-second disposable audio was submitted through the existing GUI ingest controller; the worker honored 120-second stability, ran CUDA large-v3, published raw/SRT/manifest and automatically produced waiting_ai. ASR child telemetry elapsed: 13.547 seconds (not a quality benchmark; default zh profile). After evidence capture, only these disposable workers were gracefully stopped and their autostart disabled.

Application/launcher source is unchanged from accepted UX code. Final packaging differs from the tested archive only in release documentation/manifests. No repeat of full ChatGPT→Word, long ASR, H3 or previous GREEN suites. Production and prior UX installations received no writes. Public publication is separate: local GitHub CLI login and the historical negative-test personal-path fixture must be resolved first without silently rewriting existing history.
