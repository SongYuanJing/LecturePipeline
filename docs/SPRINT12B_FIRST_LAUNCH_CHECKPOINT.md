# Sprint 12B — first-launch rollback checkpoint

Date: 2026-10-22 (Asia/Shanghai). Branch: `dev/unified-dev-vic28`; starting commit `95ebdab89e9b25948194db6d6850c6519d780da2`. This is an isolated DEV candidate, not a release. Production, Google Drive, the working workbook, real Scheduler tasks, GitHub main and published Releases were not changed.

## Cause and correction

The previous Setup.exe accepted a top-level Windows window as proof of a successful first launch. `DesktopShell` creates that window before its asynchronous `CoreWebView2Environment.CreateAsync` / `EnsureCoreWebView2Async` calls finish. The original profile-path collision therefore gave `status=updated` while the native window failed with `0x80080005`.

Before changing product code, `unified-dev-build/sprint12b/red-old-setup` reproduced that exact false success on the existing disposable `sprint11/beta4-copy`: `status=updated`, pointer dev.6, `automaticRollback=false`. The guarded test manually restored beta.4 afterward and matched all 444 tracked hashes.

Setup now supplies a unique status path inside its installation's `run` directory. The existing Python dashboard host validates that path and passes it to the native shell. The shell atomically reports `ready` only after WebView2 environment/controller initialization, or reports its exception and closes. Setup waits at most 45 seconds, rejects an exited launcher, records a per-launch diagnostic JSON in `logs`, stops an unsuccessful launcher and invokes the existing recovery-journal rollback. Tk fallback behavior for clean installation remains available. Bootstrap tests first failed for the absent acknowledgment API, then passed **32 assertions**, including delayed ready, error, exit and timeout.

## Native delivery gates

The final local DEV package is `2.0.0-beta.5-dev.7`:

| Artifact | SHA-256 |
| --- | --- |
| `unified-dev-build/sprint12b/installer/Setup.exe` (52,339,488 bytes) | `498b655d6ee902c4a969abb01ef96dee9683072527b90bc2c9b714a5cbb3e45d` |
| `unified-dev-build/sprint12b/native/LecturePipelineDesktop.exe` | `b32b999f2472ed3ccd9118688ccb7690ab5738a323f7f14abf38f0e73c0c99f7` |
| Embedded `bootstrap/payload/application.zip` | `1dda13f032a59146adb684287c98cd93d93b2131680042f71441e615350d45e3` |

- **Fault and automatic rollback:** The final Setup.exe, the same disposable beta.4-copy and the same WebView2 profile-path collision produced `status=failed`, `0x80080005 (CO_E_SERVER_EXEC_FAILURE)`, no shell process, automatic pointer return to `2.0.0-beta.4` and **444/444 unchanged tracked hashes**. The previous profile directory was restored. Evidence: `sprint12b/final-fault-setup/{observed-before-cleanup,final}.json` and the matching `app/logs/setup-webview2-*.json`.
- **Normal first launch:** A subsequent beta.4-to-dev.7 Setup.exe upgrade reported `status=updated` only after `ready`; WebView2 acknowledgment took **1,624 ms**. Exactly one visible native shell opened. Five course paths, queue IDs, lecture IDs and processed IDs remained the same. Among 444 tracked files, only `bootstrap-state.json`, `current.json` and `package-manifest.json` changed as expected; no data, external-course file or AI queue hash changed. Evidence: `sprint12b/success-final-setup/result.json` and before/after snapshots. The final post-regression snapshot still matched all 444 hashes from the upgraded state.
- **Product-mode access:** On this disposable installation only, temporarily removed the DEV marker and changed the installed release status to `beta`, then restored both exact bytes. The native host returned `vic28.dashboard/1`, `available=true`, five courses, 17 catalog entries, 39 audited reads in allowed external DEV folders, zero errors and `read_only=true`. The 444 tracked hashes stayed unchanged. This is a product-mode simulation, not a public beta package. Evidence: `sprint12b/product-mode/{result,preservation}.json`.
- **Icon and shortcut:** Extracted 32×32 icons from final `Setup.exe` and native EXE had zero pixel differences from accepted icon A. The native window title was `Lecture Pipeline DEV`. A new shortcut in the isolated empty `sprint12b/fresh-shortcuts` directory targets this copy's private `pythonw.exe`, launches the stable dashboard entry and uses the installed dev.7 native EXE icon. Evidence: `sprint12b/icon-shortcut-gate.json`.

The reused beta.4-copy also contains a **stale dev.5 WebView2 shortcut** left by earlier DEV upgrade tests. Setup deliberately preserves a pre-existing shortcut whose icon path conflicts and returns `shortcut=null`; it did not rewrite the old link. The fresh-shortcut gate above passed. Repeated DEV upgrades with stale links require a separate shortcut policy decision before a future updater release.

## One overall regression pass

The ASR Python 3.11 partition passed **13/13**. The document Python partition ran **411 tests: 4 failures, 3 errors, 2 skips**. Full output is preserved in `unified-dev-build/sprint12b/regression-{asr,document}.log`; no second full run was started.

| Group | Result and cause observed in log |
| --- | --- |
| Packaging fixture | 2 failures + 3 errors. These tests expect a synthetic isolated installation and one-word dictionary, but the run pointed `LECTURE_CONFIG` at the rebased beta.4-copy with a nonstandard DEV task prefix, five real-shaped course bindings and a populated copied workbook. Failures include `104 != 1` and invalid task prefix. This invocation does not establish a product regression. |
| Legacy shortcut test | 1 failure. Windows PowerShell 5.1 `Add-Type -Path installer/ShellShortcut.cs` cannot compile the existing `out _` discard in `IconLocation`. The final Setup.exe itself created a Unicode shortcut successfully through its compiled .NET path. The legacy PowerShell integration path remains an independent defect or test-environment incompatibility. |
| Tk catalog view | 1 failure. An unchanged-render assertion saw fractional `yview` move from `0.868421` to `0.871795` at 192 DPI; text and selection matched. This visual stability issue is independent of the first-launch change. |
| Skips | 2. The device process smoke lacked `LP_TEST_PYTHON311`; the deployment-plan test lacked an explicit disposable `LP_DEPLOYMENT_ROOT`. |

The failed regression is reported as such. Its causes were diagnosed from the saved log without changing unrelated code or starting another full test cycle.

## Checkpoint state and decision

The beta.4-copy now points to `2.0.0-beta.5-dev.7` for further isolated inspection. No matching copy/Sprint12B process, `.pending`/`.tmp`/`.partial` file in its `run` tree, or DEV Scheduler task remains. Four small setup status files and their diagnostic logs are intentionally retained. `C:\PipLine GPT WORK` uses **44.492 GiB**, leaving **5.508 GiB** under the 50 GiB cap. No large runtime was downloaded or new full Production copy made.

**GO for the specific first-launch fault/rollback fix and continued isolated DEV evaluation. NO-GO for public beta preparation or Production upgrade.** The overall regression is not green and the legacy PowerShell shortcut test needs a separate decision. Stop at this checkpoint; do not automatically start another broad run or unrelated implementation.
