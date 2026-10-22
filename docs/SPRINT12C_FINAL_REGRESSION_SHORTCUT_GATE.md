# Sprint 12C — final regression and shortcut gate

Date: 2026-10-22. Branch: `dev/unified-dev-vic28`. All installations, data, shortcuts, logs and tests in this gate are DEV fixtures under `C:\PipLine GPT WORK`. Production, Google Drive, Scheduler tasks, the working vocabulary and published releases were not changed.

## Findings and fixes

- The five packaging failures/errors in Sprint 12B came from pointing the tests at a rebased beta.4 copy with populated user-shaped data. With `PACKAGING_REPO` set to this worktree and `LECTURE_CONFIG` set to the disposable configured Sprint 10 installation, **22/22 packaging tests passed**. No packaging code change was needed.
- Both prior skips were enabled with `LP_TEST_PYTHON311` (isolated embedded 3.11) and `LP_DEPLOYMENT_ROOT` (disposable configured installation). The device-process smoke and Unicode integration plan passed.
- The 192-DPI Tk assertion compared an exact fractional `Text.yview()` coordinate. Tk may settle wrapped-line geometry on an idle update; the unchanged-data path in `CatalogPanel.render` returns before touching widgets. The revised assertion verifies the user contract: unchanged text and selection, with the reader still at the bottom. Both catalog GUI tests passed.
- Windows PowerShell 5.1 really compiles `installer/ShellShortcut.cs` when `Integrate.ps1 -Apply` is used. Its compiler rejected `out _`. Replacing that discard with a declared integer made the six first-run tests pass, including a real Unicode COM shortcut roundtrip.
- Setup previously kept its own WebView2 shortcut with a stale version-specific icon. It now updates only a link with the exact expected target, arguments and working directory and a canonical prior-version native icon. A changed target, arguments, directory or custom icon is preserved and reported as a conflict. Replacement uses a temporary link and atomic `File.Replace`. The bootstrap gate passed **36 assertions**, including stale managed link migration and preservation of a custom icon.

## Delivery evidence

Candidate package: `C:\PipLine GPT WORK\unified-dev-build\sprint12c\installer\Setup.exe`, 52,339,546 bytes, SHA-256 `4cfb51e9c7be533e51c4da0b30ede16d535de95b9d410ad46803bcfc9c38619f`. Its embedded application payload remains verified `2.0.0-beta.5-dev.7` (SHA-256 `1dda13f032a59146adb684287c98cd93d93b2131680042f71441e615350d45e3`). This is a local DEV candidate, not a public beta.5 artifact.

| Gate | Result |
| --- | --- |
| Clean Setup.exe installation | `status=ready`, dev.7 pointer, separate data and valid WebView2 link. It used copied, already verified model/components and the pinned base cache to avoid downloads; there was no existing config or data. `sprint12c/clean-install/setup-report.json`. |
| Known WebView2 profile collision | `status=failed`; automatic rollback to beta.4, 444/444 tracked hashes unchanged, profile restored. `sprint12b/sprint12c-fault-shortcut-candidate/final.json`. |
| Normal beta.4 → dev.7 Setup.exe upgrade | `status=updated` only after `ready` (1,730 ms). One visible native shell. 444 files checked; only the three expected installation metadata files changed. Data, external course paths, queue IDs, lecture IDs and processed IDs preserved. Previously stale Setup-managed shortcut now points at the installed dev.7 icon. `sprint12c/upgrade/result.json`. |
| Repeat invocation on dev.7 | Safely refused because the upgrader accepts beta.4 as its source. Pointer, config and shortcut unchanged; target and icon exist. `sprint12c/repeat-report.json`. |
| After final regression | All 444 tracked hashes equal the post-upgrade snapshot; queue and lecture IDs unchanged. `sprint12c/post-regression.json`. |
| Targeted tests | Packaging 22/22; first-run 6/6; catalog GUI 2/2; device smoke 1/1; bootstrap 36 assertions. |
| One final split regression | Document runtime **411/411**, ASR runtime **13/13**, **0 failures, 0 errors, 0 skips**. `sprint12c/regression-document.log` and `sprint12c/regression-asr.log`. |

Final DEV process and pending-file checks found none in the two tested installations. Workspace usage: **47.839 GiB / 50 GiB**, leaving 2.161 GiB. The disposable clean installation is retained for inspection, not silently removed.

## Limits and release decision

The clean installation used preseeded verified components and `--no-launch`; native launch was exercised on the separate upgraded installation. No GPU ASR run or Production upgrade was performed. An explicit engineering rollback after a *successful* upgrade does not manage external shortcuts; the supported automatic first-launch rollback occurs before shortcut creation and passed. Repeat Setup invocation on an already upgraded version is intentionally rejected rather than treated as an in-place reinstall.

**GO** for preparing the public beta.5 release candidate from this DEV checkpoint. **NO-GO to publish this exact Setup.exe as `v2.0.0-beta.5`**: the embedded application still identifies itself as `2.0.0-beta.5-dev.7`. Promote the version/release metadata, rebuild and verify the resulting release artifact separately, then request explicit publication approval.
