# Sprint 12 — integration checkpoint and delivery blocker

Date: 2026-10-22 (Asia/Shanghai). Branch: `dev/unified-dev-vic28`. This is an isolated DEV candidate. No release, main merge, Production upgrade, working dictionary, Drive source, or real Scheduler task was changed.

## Scope and storage

Work S commit `826e91df077d3a507659a8979f852f5591594f20` was integrated as local commit `030263b9c2d0cd2dae4ccae13cd3f9a22d0c3c13`: exactly seven frontend, UI test, and documentation files. Work A session token (`location.hash` cleanup and `X-Lecture-Session`), read-only host, icon A, Tk fallback, installer, and backend were preserved. The only subsequent source change makes the UI polish QA test honor isolated stale/unknown/preparing ports.

Initial DEV workspace was about 44.35 GiB. The largest areas were `unified-dev-build` (27.73 GiB), `scratch` (5.34 GiB), `unified-dev` (4.95 GiB), and `app` (4.87 GiB). Only the confirmed disposable Sprint 11 `clean-install` copy was removed (7.377 GiB) after eight log/state files and their SHA-256 hashes were preserved under `unified-dev-build/sprint12/preserved-sprint11-clean-install`. The current DEV installation, beta.4 test copy, Work S worktree, rollback backups, and unknown material were retained. Final measured workspace: 44.422 GiB, under the 50 GiB cap.

## Completed bounded checks

- Integrated read-only dashboard Python tests: **22/22 PASS**. JS syntax and staged diff checks passed.
- Browser gate on the integrated web files and isolated DEV data: baseline PASS (21 layouts), Preview 2 PASS (30 layouts), polish PASS (**135 checks, 39 layouts**). The first polish attempt failed only because three QA scenario ports were hard-coded; after making them configurable, only this suite was rerun and passed. Zero JS errors and zero external page requests were reported. Browser visual fixtures are synthetic and labeled; the real DEV viewer reads only an isolated DEV installation. QA viewers used a temporary loopback host without a token for browser layout checks; the installed native host token was verified separately.
- Built local `2.0.0-beta.5-dev.6` Setup.exe with existing pinned .NET and native icon A assets; no large component was downloaded. `Setup.exe`: 52,338,184 bytes, SHA-256 `5ab907004f68b488acf1eb44c5007384608db488700e7848a64a540736a2cd75`. Embedded payload SHA-256 `2c5294933426fae13f735b97d8473b3f10c3a5eeaf83d89fd6d08d56847c5d15`.
- Clean Setup.exe install in CPU mode from verified local cache: `status=ready`, version `2.0.0-beta.5-dev.6`. Installed WebView2 shell opened a native window titled `Lecture Pipeline DEV`; host snapshot returned 200 with one isolated DEV course, missing token returned 403, POST returned 405. Four sampled config/state/pointer files retained SHA-256 on open/close. The shell closed; no Sprint 12 install process remains.

## Blocking first-launch failure

On the disposable `sprint11/beta4-copy`, the prior DEV upgrade was rolled back to beta.4 first. Its five courses, 12 queue IDs, 12 lecture IDs, eight processed IDs and 444 tracked file hashes were recorded. An existing WebView2 profile directory was preserved under a new name within this copy, and a regular file was placed at the expected profile path to induce an actual WebView2 initialization failure. Setup.exe was then invoked with `--upgrade` and launch enabled.

**Observed:** Setup.exe reported `status=updated`, `current=2.0.0-beta.5-dev.6`, and left `current.json` pointing to the new version. The native shell showed: `Новый интерфейс недоступен ... 0x80080005 (CO_E_SERVER_EXEC_FAILURE)`. It did not provide a usable browser view. Setup's `LaunchWindow` accepts the shell's top-level window before the asynchronous `CoreWebView2Environment.CreateAsync` / `EnsureCoreWebView2Async` completes. Therefore the automatic rollback branch was not entered. This reproduces a false success in the required real first-launch rollback path.

Evidence: `unified-dev-build/sprint12/first-launch-blocker.json`, `upgrade-first-launch-fault-report.json`, and `sprint11/beta4-copy/app/logs/launch-error.txt`. After dismissing only the test error dialog, the disposable copy was manually rolled back using its new backup receipt. Its pointer returned to `2.0.0-beta.4`; all **444/444 tracked hashes** matched the pre-upgrade beta.4 snapshot. The preserved WebView2 profile was restored. No process remains in this copy.

## Gate status and next step

**NO-GO for public beta preparation or Production upgrade.** The automatic first-launch failure detection and rollback must be corrected with a readiness/failure acknowledgment from WebView2 after initialization, rather than top-level window presence. Re-run this one fault gate after that fix, then complete the postponed native product-mode external-course check, icon/shortcut comparison, and one overall regression gate. The normal beta.4-to-new-version launch was not repeated after this blocker; no public package was produced.

The isolated clean DEV installation remains available for user interface evaluation at `C:\PipLine GPT WORK\unified-dev-build\sprint12\clean-install\app`, with separate data at `...\clean-install\data`. Its shortcut is under `...\clean-install\shortcuts`. The installer is `C:\PipLine GPT WORK\unified-dev-build\sprint12\installer\Setup.exe`. These are local test artifacts and retain `distribution_status=dev`. All six Sprint 12 QA viewers were stopped; no Sprint 12 installed app or beta.4-copy process remains. Existing Work S viewer processes were left alone.