# Phase 1c — Windows 11 x64 bootstrapper

Decision: self-contained .NET 10 x64 WinForms. No installed Python or .NET runtime
is needed to launch `Setup.exe`. Windows 10 is **not** an official support target.
No updater, new release version/tag, driver installation, global PATH change or
Task Scheduler integration is included.

## Ownership boundary

`bootstrap/InstallEngine.cs` handles the pre-Python base only: download the pinned
official release ZIP over HTTPS, verify exact size/SHA-256, extract to an owned
staging directory, verify the base per-file manifest, apply the embedded current
source payload and verify it. Publish the verified files, then call the packaged
private Python explicitly. Neither global Python nor pip participates.

`bootstrap/base.json` pins the existing `v1.9.5-beta.1` asset. The source payload
is generated from this checkout by `scripts/build_bootstrap_payload.py`, contains
current launcher/application code and requirement manifests, and is embedded in
Setup. This avoids publishing a replacement under the old tag or using `main`
as a feed. It does not claim a reproducible supplier build of the historical base
Python ZIP. A later release can deliberately pin a new qualified base artifact.

`installer/bootstrap_flow.py` is a JSON-lines bridge, **not a dependency resolver**:

1. Read hardware inventory and the selected mode (preserve existing config on retry).
2. Invoke existing `download_components.install('required')` for PyAV/CT2/model.
3. In GPU, obtain CUDA; in Auto, NVIDIA inventory is only a download hint. CPU
   does not download CUDA. Full Phase 1b probe remains the authority for GPU readiness.
4. Use existing `setup.configure`, Phase 1b selection and actual `component_status`.
5. Hand success back to .NET. The shell creates the per-user shortcut and launches
   the existing private Python stable launcher, confirming its main window.

No component supplier versions, hashes, model resolution, probes or import rules
are reimplemented in C#. Runtime/components/models remain outside `versions/`;
the current pointer and stable launcher layout remain suitable for a later
side-by-side updater. This Setup deliberately refuses another payload identity.

## State, retry and cancellation

- `bootstrap-state.json`: schema 1, payload SHA-256 identity (`bundle`), absolute
  data root, and `installing`/`ready`/`cancelled`/`failed`. It is installation
  metadata, not a new application config schema. Unknown nonempty roots are refused.
- `bootstrap.lock`: exclusive lock while setup runs. One installer owns a root.
- `bootstrap-base-ready.json`: records completed base publication. Every rerun
  verifies the package's file hashes before launching private Python.
- `cache/bootstrap/<sha>.zip`: verified base cache. `.part` is never accepted.
  Component cache and component imports remain owned by Phase 1a.
- `bootstrap-cancel`: cooperative Python cancellation request. Download checkpoints
  run between chunks; import/probe/publication finish at their safe boundaries.
  Closing the window requests cancellation and waits. A blocked read is bounded
  by a timeout. Verified files are retained. Large pinned artifacts retain a
  checksummed resumable prefix; small incomplete downloads are removed. See
  [RESUMABLE_DOWNLOADS.md](RESUMABLE_DOWNLOADS.md) for the bounded HTTP contract.
- A cancelled fresh setup cannot be launched as a completed app: `launch.py`
  checks the bootstrap state when present. Legacy installations without this
  metadata keep their old behavior. Cancelling verification of a previously
  ready installation retains `ready` and does not invalidate its usable copy.
- New data is initialized in an owned sibling directory. `bootstrap-data.json`
  journals publication and configuration fixup. A crash before config creation
  can retry the owned unpublished data; a crash after data rename finishes config
  without replacing user files. Nonempty unrelated data roots are never adopted.
- `logs/bootstrap-python.log`, `bootstrap-health.json` capture real stages and
  selection/component results. Failure does not produce a success report.

Directory selection accepts spaces and Unicode. Local paths through reparse
points are refused; paths must be separate. Install root is limited to 110
characters because final private-model paths still obey native Windows limits.
An unwritable location yields a clear error recommending a per-user directory;
the executable manifest uses `asInvoker`, not automatic elevation.

The normal shortcut lives under the user's Start menu `Programs/Lecture Pipeline`
and contains an install-specific suffix. It targets private `pythonw.exe` plus
`launcher/launch.py gui`, with the installation working directory. Conflicting
shortcuts are preserved. Its lifecycle is independent of worker scheduled tasks.
Disposable tests redirect the same shortcut implementation into a test directory.
Native Unicode paths use `IShellLinkW`/`IPersistFile`; the WScript automation
interface rejected a real Unicode target during the disposable gate.

Offline/manual fallback is retained through `ImportPyAV.cmd`,
`ImportCTranslate2.cmd`, `ImportModel.cmd`, `ImportCUDA.cmd`. The Advanced button
opens the install folder and explains these commands; Retry reuses valid imports.

## Build and checks

SDK pinned by `bootstrap/global.json`: 10.0.401. The observed bundled runtime is
.NET 10.0.12. Build with a development Python and this SDK (build-time tools only):

```powershell
./scripts/publish_bootstrap.ps1 -Python <build-python> -Dotnet <dotnet-executable>
dotnet run --project tests/bootstrap/Bootstrap.Tests.csproj -c Release
python -B -m unittest discover -s tests -p test_bootstrap_flow.py -v
```

Publish is self-contained `win-x64`, single-file, native libraries included,
compression enabled and trimming disabled. First launch extracts bundled native
runtime libraries to the standard per-user .NET bundle cache; it does not install
a global .NET runtime. `Setup.sha256.json` records the actual artifact.

The Actions workflow builds an **unsigned candidate artifact**, runs targeted
tests and does not publish a release or write repository contents. Remote Actions
execution is not claimed while GitHub write access is unavailable.

Prototype measured before full flow: 51,633,067 bytes; fresh bundle-cache process
wall 2.460 s / WinForms shown 1.964 s; warm process wall 0.421 s / shown 0.125 s.
These are local one-run measurements, including process overhead, not guarantees.

Diagnostic arguments automate the same UI/engine, not an alternative installer:
`--run --install <absolute> --data <absolute> --mode auto --report <file>`.
`--shortcut-directory <disposable>` redirects test shortcuts; `--no-launch`
avoids opening another GUI on verification runs. `--cancel-after-ms` exercises
the same Cancel handler. Optional `--smoke-audio` performs real ASR using the
saved config and records backend/timings, without lecture state/publication.

## Native acceptance — 2026-10-04

**Native-qualified on the current Windows 11 x64 / RTX 3050 6GB Laptop host.**
This is not general release readiness or clean-Windows VM certification.
Machine-readable evidence: [phase1c-native-2026-10-04.json](phase1c-native-2026-10-04.json).

Final source commit: `ad130ef082686a0f66e16dbf4a8e3d6048e0c528`.
Final `Setup.exe`: **51,806,987 bytes**, SHA-256
`329d63336793cbd74c32c0d642cccb975948d5efc9e015759243df7d4b9e3869`.
The local artifact is `.local/bootstrap-resume/Setup.exe`; it is not published.
No release version/tag was changed. No push was attempted while write access
remained unavailable.

All installation actions ran through this compiled EXE into a new disposable
root `%TEMP%/LP1c-20261004c/Программа 课程`; data and test shortcuts are siblings
`Данные 课程` and `Ярлыки 课程`. Production, baseline and previous user test data
were not modified. No component/model was copied from another installation.
PATH contained only Windows System32; DOTNET_ROOT pointed to a nonexistent folder.

| Check | Observed result |
| --- | --- |
| Private base | Actual pinned GitHub Beta ZIP downloaded; 80,109,954 bytes, SHA-256 and package files verified |
| Supplier components | PyAV 18.1.0, CTranslate2 4.8.2, five large-v3 files at pinned revision, cuBLAS 12.9.2.10 and cuDNN 9.10.2.21 downloaded/imported; all nine supplier SHA-256 values match |
| Cold cache | One base ZIP and nine unique supplier artifacts initially absent; acquired by the real downloader |
| Native Cancel/Resume | Cancel retained 154,140,672 bytes, matching prefix hash and `cancelled` state; no ready model file. Retry validated HTTP 206/range/ETag and resumed from that offset |
| Automatic resume | Additional bounded retries resumed at 1,518,213,274 and 3,086,882,970 bytes. Final 3,087,284,237-byte model passed full SHA-256 and import. The log records retries/offsets, not the low-level transport exception |
| component_status | Base, PyAV, CT2, model and CUDA `Valid`; CPU capability `Available`. Lightweight GPU capability intentionally remains `Unverified`; full setup probe and ASR separately verified CUDA |
| Auto/backend | Auto selected `cuda`, `int8_float16`; real private model/inference/VAD probe passed |
| Real ASR | Public 11-second JFK fixture; nonempty transcript; `actual_device=cuda`, no CPU fallback; model load 8.625 s, transcription 1.657 s, child wall 11.204 s |
| Main GUI | Confirmed private pythonw process and exact `Lecture Pipeline · 1.9.5-beta.1` window after setup and warm rerun |
| Warm installer | Success in 53.924 s; installed components reused; config, external data and shortcut SHA-256 **and mtime** unchanged |
| Cache verification | Nine explicit `fetch` calls through installed private Python returned `Verified cache`, no supplier download |
| Shortcut | IShellLinkW target/arguments/working directory verified; actual Unicode .lnk opened main GUI in 1.409 s; GUI closed cleanly |
| Final state | `ready`; no `.part`/`.partial` left; application closed after tests |

Cold wall time was **2,184.941 s (36 min 25 s)** from first EXE launch to ready,
including the deliberate cancellation, verification pause and resume. Executing
installer processes accounted for 195.434 + 1,968.006 s. This is a network-bound
recovery-inclusive observation, not a clean uninterrupted performance benchmark.
Final EXE startup with a new bundle cache was 0.669 s; warm startup 0.576 s.

Targeted verification: **21 downloader tests (12 existing + 9 resume), 8 bootstrap
flow tests and 22 .NET assertions passed**. Earlier Phase 1b ASR tests and native
CPU/Auto/GPU qualification remain documented separately; CPU inference was not
repeated merely to enlarge this Phase 1c gate. Cancellation and failure tests do
not mark incomplete installs ready; existing unrelated data is preserved.

## Reviewable implementation commits

| Commit | Slice |
| --- | --- |
| `df39909` | Minimal self-contained WinForms prototype and startup measurement |
| `d58bea0` | Python bridge, cancellation, recoverable setup and launch guard |
| `49a82ae` | Pinned private base installation, progress and Python handoff |
| `fb4f5c5` | Local publish script and unsigned GitHub Actions build |
| `62dbea3` | Measured high-DPI layout defect |
| `c47e84b` | Bundled .NET runtime license/notices |
| `e35864c` | Launch-guard and CPU/CUDA download policy tests |
| `08ff793` | Real ~20-second Windows inventory required a 30-second timeout |
| `63d375b` | Real Unicode shortcut failure fixed using IShellLinkW |
| `ad130ef` | Large-artifact timeout recovery: bounded resumable downloads |

The last fix changes `installer/download_components.py`, the additive model
size pin in `components/model-manifest.json`, `tests/test_resumable_downloads.py`
and [RESUMABLE_DOWNLOADS.md](RESUMABLE_DOWNLOADS.md). Earlier cancelled candidates
remain diagnostic evidence; they are not qualified installations. Phase 1c is
complete for this host. **Stop here; do not start Phase 2 automatically.**

## Release limitations

- No signing certificate or release publication was requested. An unsigned EXE
  can trigger SmartScreen/AV. SHA-256 pins protect downloaded bytes; distribution
  signing/reputation must be handled before a public release candidate.
- The current-host gate does not certify a clean Windows VM. Existing Microsoft
  VC v14 prerequisite of native ASR remains as documented in PACKAGING.md; it is
  not silently installed globally. Missing native prerequisites surface errors.
- Large pinned model/CUDA downloads resume with bounded retries. Suppliers that
  ignore Range require a whole-body restart; imports/hash/probes can delay a
  cancellation boundary. No full disk-capacity reservation is implemented.
- A different payload is refused rather than updating an existing installation.
  Phase 2 updater and data adoption/migration remain out of scope.
