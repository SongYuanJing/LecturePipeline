# Sprint 11 — Safe Upgrade & Delivery gate

Date: 2026-10-22 (Asia/Shanghai). Branch: `dev/unified-dev-vic28`, starting from `ad32fb36afa04e99b593b76a4cf8f79651fa5f7a`. This is a local DEV candidate, not a published release. VIC-30 and Work S UI polish are excluded.

## Local artifacts

| Artifact | Path under `C:\PipLine GPT WORK\unified-dev-build\sprint11` | SHA-256 |
|---|---|---|
| Full native installer | `installer-final\Setup.exe` (52,337,215 bytes) | `692fd8dd54700555bf83cbe3f3692f5e0023c313a83e140fbb6eec90f5bd7fc5` |
| Embedded application ZIP | `payload-final\application.zip` (547,605 bytes) | `9860692ae2994b4c266d3790f2e15996bc0e792aee650759f9794682a709964b` |
| Payload manifest | `payload-final\application.json` | `4d768a51f6bb6fadb5ef811360e301b6099cfd3c40f47884cd9c3f8e88a03b06` |
| Native WebView2 EXE | `native-icon-a\LecturePipelineDesktop.exe` | `e161c8014a5f6cd64cf9370b22f9b2ed0c596c493ee6bcd553b6ae3ca639be59` |

The installer embeds the ZIP and manifest. Build used the pinned local .NET SDK 10.0.401 ZIP at `C:\PipLine GPT WORK\toolchains`, verified against Microsoft's SHA-512 release metadata. No machine-wide SDK or PATH change was required. The accepted beta.4 release/tag/assets and GitHub main were not changed.

## Paths and behavior

- **Clean install:** launch `Setup.exe`, select separate empty install and data directories. Setup verifies its embedded payload, downloads or reuses SHA-pinned base/components, creates data and config, and installs a WebView2 shortcut. The Tk launcher remains available as `Lecture Pipeline (Tk).vbs`. In this DEV build, installation and data must be sibling folders inside one candidate directory. `bootstrap_flow.py` now updates the DEV marker from its temporary data path to the final data path before installation becomes ready.
- **beta.4 upgrade:** use explicit `Setup.exe --upgrade` with the existing install and data paths. The full embedded payload introduces the launcher and native shell which the old code-only updater cannot deliver. The Python transaction checks the beta.4 release, data root, payload inventory and SHA-256, and idle sessions/workers. It backs up replaced installation metadata and launcher, writes a recovery journal, switches the version pointer, performs health checks, then marks the install ready. The old version directory, config, user data and Scheduler definitions remain. A rollback restores exact prior bytes; an identical staged version may be reused on retry, while differing bytes are refused.
- The installed WebView2 host is loopback-only and read-only, with a session token, origin check, GET-only API and explicit read roots from validated config. DEV candidates retain their separate marker fence. The existing Python backend, queue and Tk GUI remain the authority.

## Native evidence

- An initially empty DEV target was installed using the final Setup.exe. A first pass was cancelled through the installer's supported checkpoint to reuse verified downloads from an already copied DEV cache, then the same Setup resumed. Final report: `status=ready`, exit 0; the marker names the final data folder. The clean WebView2 window opened, returned HTTP 200 with `available=true` and one new course, and rejected POST with 405. Tk fallback opened with title `Lecture Pipeline · 2.0.0-beta.5-dev.5`; Windows returned nonzero small and large icon handles.
- A full disposable copy of the working beta.4 installation, data and 15 external course folders was rebased inside `beta4-copy` before any launch. JSON paths were redirected only in the copy, including file-URI AI identities. Five course IDs, 12 lecture IDs, 12 queue IDs, eight processed records, languages and ASR settings survived rebasing. All 364 non-JSON data/course files kept their SHA-256 values. The dictionary hash is `2e593eb91dc34a6f37a3ccb8f70f29075598fc3a5a15137c42fa3180c4b7ea34`.
- Setup upgraded that copy successfully. Preflight passed with 5 subjects and `AUTO → GPU` with CPU fallback. The native dashboard opened and read five courses, 17 catalog entries and one pending item. Its snapshot request returned 200; missing session token and foreign Origin returned 403, POST returned 405. The host bound only `127.0.0.1` and its profile stayed under the copy. Closing the window released the host port and processes.
- Explicit rollback restored beta.4's `current.json`, launcher, updater and VBS byte-for-byte. An injected exception immediately after launcher replacement on the same actual copy restored seven tracked installation/config/queue files with no journal left. Final Setup retry then succeeded, reusing only the matching version directory. Of 444 tracked files, only `bootstrap-state.json`, `current.json` and `package-manifest.json` differed between the rebased beta.4 copy and final upgraded copy. Course, lecture, queue, processed-state, config and all copied data/media hashes were unchanged.
- Both `Setup.exe` and the installed `LecturePipelineDesktop.exe` contain the nine exact frames of the accepted dark ICO. The Tk ICO hash equals the accepted dark ICO (`4fc082075aadbeb6f688e9ed8dd556749df2051ae88014fbdeb45e68217ee6a6`). The new LNK points at the installed native EXE for its icon. No test AppUserModelID was copied. Existing pinned shortcuts and Windows icon cache were not changed.
- The old beta.4 updater refuses a manifest with `updater_protocol=2` before switching its pointer, covered by the updater regression. This new full installer is independent of the old code-only update path.

## Regression and boundaries

The seven related Python modules passed **61/61** tests: safe upgrade 7, bootstrap flow 9, delivery payload 1, updater 13, update contract 2, update GUI 7, VIC-28 read-only dashboard 22. Native bootstrap harness passed **27 assertions**. Exact output is in `unified-dev-build\sprint11\test-results`. The actual-copy fault report and three data/hash snapshots are under `unified-dev-build\sprint11\actual-copy-fault-report.json` and `beta4-copy\verification`.

At final audit, `C:\PipLine GPT WORK` occupied 44.35 GiB (<50 GiB), no Sprint 11 processes or DEV Scheduler tasks remained, Production Lecture stayed Running and Dialogue Disabled, Production pointer stayed `2.0.0-beta.4`, and the live dictionary SHA-256 matched the untouched copied workbook. No Google Drive source was written.

**GO for isolated user evaluation of the DEV application. NO-GO for public beta or Production upgrade.** The DEV-only version policy and marker are not a public-release contract. Setup's automatic first-launch failure/rollback path was code-reviewed and the Python rollback was exercised, but an actual WebView2 launch-failure rollback through Setup.exe was not triggered. No new end-to-end ASR or worker processing was run in this delivery gate; component probes and the previously accepted Sprint 10 ASR smoke cover that path only partially. Product-mode external course access has a unit test but no native public beta package gate. User visual acceptance, native public upgrade rehearsal, and the separate Work S UI polish integration remain future gates.
