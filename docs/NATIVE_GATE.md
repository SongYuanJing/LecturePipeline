# Phase 1a + 1b native qualification — 2026-10-04

**Passed on this host**, using code `192b08bb6ca5ceee035ceafa51af0afef1701332`
on `feature/bootstrap-downloads`. This closes the real supplier/native gate for
this Windows 11 / RTX 3050 host. It does not certify fresh Windows, Windows 10,
other drivers/GPUs or a release candidate. Phase 1c has not been implemented.

Machine-readable measurements, artifact SHA-256 values, private module paths and
component status are in [native-gate-2026-10-04.json](native-gate-2026-10-04.json).

## Isolation and provenance

- Clean candidate: `<checkout>/.local/native-gate/c04`; separate disposable data:
  `<checkout>/.local/native-gate/data04`. No production/Beta/existing test-root
  files, workers, tasks, system PATH or drivers were changed.
- Existing package builder used private base runtimes from a freshly downloaded
  official `v1.9.5-beta.1` release ZIP, verified against its SHA-256. This is an
  explicit donor for this test, not an implementation of fresh-Windows bootstrap.
  Current source/manifests were packaged over that base by `build_package.py`.
- Candidate ZIP: 80,131,923 bytes, SHA-256
  `90589cc62a3337664dfb970f12ae6b48ebb5d8455ce24eebb0c2d0177f3f6e36`.
  Its internal beta version is unchanged; it must not replace the published tag.
- Real Phase 1a downloader fetched every supplier artifact into an initially
  empty candidate cache. No component was copied manually to bypass an importer.
- Public Whisper test audio `jfk.flac`, 11.0 seconds; no user lecture used.
  Real private CPython 3.11.9, PyAV, faster-whisper and CTranslate2 performed all
  probes/inferences. No fake modules, model or inference results in this gate.

## Supplier/import/cache results

| Supplier artifact | Pin | Result |
| --- | --- | --- |
| PyAV Windows wheel | 18.1.0, cp311-abi3 | Download SHA-256, wheel checks and private native import passed |
| CTranslate2 Windows wheel | 4.8.2, cp311 | Download SHA-256, wheel checks and private native import passed |
| Systran/faster-whisper-large-v3 | revision `edaa852ec7e145841d8ffdb056a99866b5f0a478` | All five files downloaded, SHA-256 verified and imported |
| NVIDIA cuBLAS CUDA 12 wheel | 12.9.2.10 | Wheel SHA-256 and pinned DLL extraction/import passed |
| NVIDIA cuDNN CUDA 12 wheel | 9.10.2.21 | Wheel SHA-256 and pinned DLL extraction/import passed |

The model files are `config.json`, `model.bin`, `preprocessor_config.json`,
`tokenizer.json`, `vocabulary.json`. CUDA verifies all 11 DLLs in the committed
manifest. The JSON evidence contains all nine supplier filenames, byte sizes and
full hashes. Base faster-whisper version is 1.2.1.

Cold cache: nine distinct misses, all eventually downloaded and verified. One
real cuDNN read timed out; the downloader removed its incomplete temporary file.
Retry reused verified cuBLAS and downloaded cuDNN successfully (377.07 seconds
for that retry). No hash/import relaxation or network workaround was introduced.
Whole-file retry is the existing contract; byte-range resume is not implemented.

Warm cache: all **9/9** explicit calls to the real `fetch` returned
`Verified cache`, after rehashing the bytes. Actual CUDA installation also reused
both verified wheels. Repeating both `required` and `cuda` installation commands
returned `already verified` for all four component groups.

Required download/import took 1160.24 seconds; CUDA extraction/import from cache
took 28.50 seconds. These include local I/O/network conditions, not benchmarks.

## Native device results

Before CUDA installation, actual `component_status` reported base/PyAV/CT2/model
`Valid`, CUDA `Missing` (optional for CPU), CPU `Available`, GPU `Blocked`.
Setup persisted CPU in schema-1 configuration, then a fresh Config instance
selected the actual ASR backend. CUDA wheels were only cached: the runtime CUDA
directory did not exist during CPU inference.

After CUDA installation, all five component groups were `Valid`, CPU `Available`.
Quick GPU capability intentionally remains `Unverified`: full model/inference/VAD
probe is the readiness authority, not hardware inventory or DLL presence.

| Requested mode | Actual device / compute type | Selection including probe | Inference wall | Model load | Transcribe |
| --- | --- | ---: | ---: | ---: | ---: |
| CPU, CUDA directory absent | cpu / int8_float32 | 10.38 s | 21.20 s | 9.45 s | 10.73 s |
| Auto | cuda / int8_float16 | 23.59 s | 12.67 s | 9.75 s | 1.88 s |
| GPU | cuda / int8_float16 | 24.59 s | 11.80 s | 8.89 s | 1.76 s |

All three produced nonempty speech transcripts and successful child results.
Auto/GPU exercised real full GPU probes and VAD; neither fell back to CPU.
Forced GPU had `allow_cpu_fallback=false`. Each mode was written to disposable
configuration and reread by Config before `new_model`/ASR invocation.

Host: Windows 11 Pro 10.0.26200, NVIDIA GeForce RTX 3050 6GB Laptop GPU,
6144 MiB VRAM, driver 616.92. These are single-run smoke measurements, not a
transcription-quality comparison or a guarantee of memory for long lectures.

## Defects fixed in separate commits

1. `0936f37`: locked PyAV/CT2 wheel staging no longer appends a 32-character UUID
   to the full component basename. Short sibling names retain the exclusive lock,
   interrupted-stage cleanup, hash/RECORD/ABI/native checks and atomic publication.
   The original PyAV failure had a valid final path but a staging DLL path of
   261 characters. Regression covers a long install root for both importers.
2. `7064948`: model staging uses a short sibling directory instead of appending
   `.pending` to the full revision. Reproduced final path 256 / old stage 264
   characters; exact long-path regression added, all model hashes retained.
3. `192b08b`: download temporary files use a short unique basename within the
   hash directory. Actual cuBLAS final cache path was 249 / old temporary 263
   characters. Regression uses the long supplier wheel filename; uniqueness,
   streaming SHA-256, incomplete-file cleanup and atomic replace remain intact.

c01/c02 exposed the path failures; c03 was an unused intermediate build. c04 was
built in a new directory after all three fixes and ran the full gate from an
empty cache. Earlier downloaded components were not transplanted into c04.

Targeted validation: 18 tests for staging + thin package + CT2 importer on
CPython 3.11.9, and 12 downloader tests on development CPython 3.12.14 passed.
The earlier Phase 1b policy/config/failure tests remain documented separately.

## Remaining boundaries

- 1a/1b native supplier/inference gate is now closed **for this host and code**.
  A release candidate still needs its own packaged-artifact validation. General
  Windows/driver coverage, first-run visual/DPI checks and long-lecture capacity
  are not established by this short gate.
- Short staging fixes do not promise arbitrary-length final Windows paths.
- Slow-network whole-file retry, cache/disk space, byte progress and cancellation
  remain documented installation limitations; no unrelated hardening added.
- Fresh Windows without donor Python/Tk/base dependencies remains Phase 1c.
  See [BOOTSTRAPPER_OPTIONS.md](BOOTSTRAPPER_OPTIONS.md) for the decision proposal.
- No new config/data contract changed in these fixes. All commits are local;
  push the complete `feature/bootstrap-downloads` branch after write access is
  restored. Do not force-push or publish/replace a release as part of this work.
