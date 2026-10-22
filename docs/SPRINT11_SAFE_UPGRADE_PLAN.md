# Sprint 11 — Safe Upgrade & Delivery

## Goal and boundary

Deliver a local DEV Setup.exe that can install the new read-only WebView2 shell from a verified payload or upgrade an isolated beta.4 copy while retaining data, configuration, course identity, queue and rollback. No Production, Google Drive, live Scheduler task, main branch or Release mutation. Keep XLSX schema 1.4 and existing Python backend.

## Verified starting point

- beta.4 `launcher/updater.py` exactly matches the repository version. It accepts only updater protocol 1, updates `versions/<version>` and `current.json`, and launches Tk. It cannot introduce the new launcher or shell. An incompatible package must be refused before writing the version pointer.
- `bootstrap/InstallEngine.cs` currently accepts only a new/empty install and data root, and creates a Tk shortcut. `scripts/publish_bootstrap.ps1` omits the WebView2 build arguments.
- The dashboard currently requires a DEV marker and rejects configured course paths outside the candidate tree. A product upgrade needs explicit read-only roots derived from the validated config, not an unrestricted filesystem reader.
- The exact .NET SDK 10.0.401 is available as a local, SHA-512 verified archive at `C:\PipLine GPT WORK\toolchains`; no system SDK or PATH change is needed.

## Chosen path

Keep the old updater unchanged. A new external Setup.exe carries a complete versioned code payload including launcher, WebView2 shell and selected icon. For beta.4, its explicit upgrade mode first validates the installed release, selected data root, and idle GUI/workers. It stages and hashes the payload, snapshots the installation metadata it will replace, then writes a recovery journal. The commit boundary updates launcher and `current.json`; a failed first launch or interrupted commit restores the previous bytes. The user data root, config, course files and worker task definitions are not rewritten by the upgrade. No new worker is registered or launched by Setup.

For tests, copy the beta.4 installation and data into a DEV folder and rebase all configured external course folders to DEV fixtures before running the upgrade. Preserve IDs, language, ASR mode, queue and dictionary; use a fresh DEV task prefix and register no tasks. Compare semantic projections as well as file hashes. Clean install uses the existing Setup path with a shell-capable payload and Tk fallback. Neither path changes the accepted beta.4 tag/assets.

## Tasks and checks

1. **Toolchain and payload.** Build a deterministic local payload from the selected WebView2 binary and icon A; publish Setup.exe with the exact local SDK. Verify SDK, payload and executable hashes. Test clean install in an empty DEV target, launch WebView2 and Tk, and run Preflight.
2. **Upgrade transaction.** Add a narrow upgrade module and Setup entry point. Test wrong version/path/task ownership rejection; interrupted stage; rollback after pointer/launcher publication; retry; successful upgrade. Compare data/config/history/queue and preserve the old version directory.
3. **Data access and icons.** Permit read-only snapshot access only to validated configured data/course roots; preserve media-content exclusion and write fence. Integrate chosen icon into native shell, Tk fallback, Setup and shortcuts without copying the test AppUserModelID. Test loopback denial, external-path allowlist, native window icon and shortcut icon.
4. **Real copy gate.** Rebase a full beta.4 copy into DEV, run upgrade and injected failure, open the GUI, read all course identities/states/queue, run a short isolated processing check, and verify no Production paths or DEV tasks remain. Record exact gaps and GO/NO-GO; no release.

## Risk focus

- An old beta.4 updater must reject the new full-package protocol without changing its pointer.
- A copied config must never retain a writable `G:\` or Production destination.
- A crash during replacement of `launcher` and `current.json` must be recoverable before any GUI/worker starts.
- An existing custom shortcut or foreign Scheduler task must be preserved and treated as a conflict.
- A new dashboard must not gain write access or arbitrary external-file reads through course bindings.
