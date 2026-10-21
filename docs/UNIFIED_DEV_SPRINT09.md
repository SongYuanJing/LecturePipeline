# Sprint 09 — Unified DEV application

## Scope and provenance

Integration branch: `dev/unified-dev-vic28`, based on the accepted backend branch
`dev/vic26-vic27-ai-queue-integration` at `4095045ee69eff9cf282cc91346816405072f177`.
Work S UI commit `e51c71348102b05e1fa4005151b594c8919937a3` was merged without
editing its source worktree. Common base is main `c256ae3beee5c014478a833c1d156e14d0b32a8c`.
VIC-30 is not included. No public release or production installation is updated.

## One application, one backend

`installer/launch.py dashboard` loads the versioned `src/app` backend through
`gui_web/readonly_snapshot.py`. The adapter uses the existing `Config`,
`lecture_catalog`, `lecture_progress`, and AI queue files. It has no worker,
course, AI import, dictionary, or updater command bridge. The .NET Framework
4.8/WebView2 executable is a window only; it owns no pipeline state.

The dashboard host binds `127.0.0.1` on an ephemeral port. Snapshot requests
require the exact loopback Host, same Origin when supplied, and a random
per-launch session token. The token is delivered to UI JavaScript in a URL
fragment and removed from browser history after load. All non-GET methods are
rejected. The WebView2 shell blocks off-origin navigation, new windows,
permissions, and non-GET requests; host objects and devtools are disabled.
The backend read fence rejects mutations, child processes, and media/dictionary
content reads while building a snapshot. The browser itself writes only its
own profile/cache under the isolated install's `run` directory.

The installed dashboard requires a `DEV_CANDIDATE.json` marker and a DEV
release identity. Data must be in a sibling `data` folder. Course bindings
must remain inside this candidate root. Setup creates the marker for a fresh
DEV package; a normal beta package does not. Existing course paths outside
the candidate can still be read by the standalone audit host only when
explicitly allowlisted, but the packaged candidate refuses them.

## Installation and entry points

The independent tested installation lives at
`C:\PipLine GPT WORK\unified-dev\app`, with data at
`C:\PipLine GPT WORK\unified-dev\data`. Its unique task prefix is stored in
`config/config.json`. No Task Scheduler job was registered for Sprint 09.
The 2-second fixture lecture and its results live only in that candidate.

- `Lecture Pipeline DEV.vbs`: native read-only WebView2 dashboard.
- `Lecture Pipeline (Tk).vbs`: existing Tk GUI with established controls.
- `Lecture Pipeline.vbs`: backward-compatible Tk entry point.

The portable build command is `scripts/build_package.py --components <existing
private runtime directory> --desktop-bin <locally built WebView2 shell> --version
<new DEV version> --out <new output directory>`. The shell is built with
`scripts/build_desktop_shell.ps1` from existing local WebView2 SDK DLLs and
the Windows .NET Framework compiler. These machine components are copied
into the private package; their original locations are not a product runtime
dependency. No component download is performed.

`scripts/build_update.py --source <portable/versions/version> ...` creates a
code-only version archive including the dashboard. Updater stage/health checks
the dashboard/backend path and keeps the existing Tk first-launch receipt.
The updater does **not** replace `launcher/` or install a new desktop shell
into an old beta.4 installation. A full isolated DEV package is required to
introduce this shell; code-only updates work within an already compatible DEV
installation. GitHub update discovery still has no Sprint 09 release to find.

`scripts/build_bootstrap_payload.py` includes the UI/native files and DEV
identity when `--desktop-bin` is supplied. The source payload can be checked
locally. A newly compiled Setup.exe was not part of this gate because a .NET
SDK build toolchain is not present on this machine; the portable `Setup.cmd`
path was exercised instead.

## Operations

| Operation | New dashboard | Existing Tk GUI |
| --- | --- | --- |
| Read current lecture, Inbox, worker, course, AI queue states | Yes | Yes |
| Search/filter and inspect details | Yes | Yes |
| Start/stop workers, configure courses | No | Yes |
| Add lectures, AI export/import, dictionary actions | No | Yes |
| Preflight/update controls | No | Yes |

The dashboard contains no fake control that mutates the backend. Open the
separate Tk entry point for those tasks.

## Gate evidence and limitations

- Independent package preflight passed against the copied local model,
  private runtime, config, data, and dictionary.
- A short 2-second WAV passed through the real packaged CPU worker to
  Raw/SRT/manifest; the queue projected it to `waiting_ai`. A repeated worker
  cycle left the record and output hashes unchanged.
- The already-open WebView2 host changed from zero to one lecture without a
  restart. GET returned DTO `vic28.dashboard/1`; POST returned HTTP 405.
  State, AI ledger, queue, and dictionary SHA-256 remained unchanged after
  interface requests.
- The code-only DEV update passed stage/health. Injected first-launch failure
  restored the exact version pointer and retained data; the subsequent real
  update opened the Tk fallback and kept data unchanged.
- The targeted integration regression passed 146/146 tests. An attempted
  all-repository run in private document Python ran 413 tests with 5 failures,
  4 errors, 2 skips. Two multipart failures reproduced identically on the
  unchanged backend integration branch; other failures include tests requiring
  private Python 3.11, a missing historical `v1.8.1` ref, and baseline package
  assumptions. They are not counted as a passing full-suite gate.
- Work S previously verified the visual design in its native QA host at 200%
  DPI and with Microsoft Pinyin. The integrated window started and served a
  live snapshot, but automated screen capture was unavailable in Sprint 09.
  Final visual acceptance, native 125/150% DPI, screen reader, and Setup.exe
  compilation remain separate gates.

No Production worker, Google Drive original, working Excel, existing release,
GitHub main, or Work S worktree was modified.
