# Online components (development branch)

This is the first bootstrap slice. It still needs a built package containing the
two private Python runtimes. It is not a standalone Setup.exe and must not be
copied over an installed Beta: launcher hashes belong to its package manifest.

In a newly built package, open Components and choose **Скачать обязательные
компоненты**. It obtains pinned PyAV, CTranslate2 and large-v3 directly from their
suppliers, verifies SHA-256, then invokes the existing importers. Offline selection
remains available. **Скачать CUDA для GPU** is separate and optional for CPU use.
Hardware recommendation and first-run CPU/GPU selection are the next slice.

Command-line equivalents from the package folder:

```
DownloadComponents.cmd required
DownloadComponents.cmd cuda
```

Individual component names `pyav`, `ctranslate2`, `model` are also supported.
No pip execution, system Python installation, driver installation, global PATH
change, task registration or user-data initialization occurs in this command.
Supplier terms are not accepted automatically. Existing invalid installed
components are preserved and reported rather than replaced.

The application-owned `cache/downloads/<sha256>/<filename>` retains verified
downloads across retries. Files are streamed to unique `.part` files, hash-checked
and atomically published to the cache. Handled download failures remove the
partial file; a killed process may leave an unused `.part` file. Resume is at
whole-file granularity, not HTTP byte ranges. Installed valid components skip the
network entirely. Model URLs use a fixed revision, not a moving branch.

Allow approximately 3.1 GB for the model download and 1.25 GB for CUDA wheels,
plus wheels, installed components and temporary import copies. Cache is retained;
there is no automatic space reclamation or pre-download free-space guarantee in
this slice. Do not close first-run/component UI while an operation is running.
The GUI reports the operation as running; per-file messages are currently visible
in the command-line tool. Cancellation and byte progress belong to phase 1c.

CUDA wheel source URLs were checked against exact-version PyPI metadata; existing
wheel size/SHA-256 pins match. Only DLL basenames listed in the checked-in manifest
are extracted; each DLL is verified again before the existing CUDA importer runs.

Validation: `tests/test_component_downloads.py` covers corrupt cache repair,
network interruption, wrong hash/size, unsafe source input, importer isolation,
real model/CUDA fixture import and reuse, GUI dispatch and package entry hashes.
Tests use temporary fixtures, not user installations. Real multi-GB download and
private-runtime/native smoke are still release gates; passing unit tests does not
close the clean-install gate.

Update 2026-10-04: the real supplier/native gate passed in a new disposable
candidate on Windows 11 / RTX 3050, after three isolated long-path fixes. See
[NATIVE_GATE.md](NATIVE_GATE.md) for hashes, cache reuse, native imports and real
CPU/Auto/GPU inference. This qualifies that host, not fresh Windows or a release.

## Development validation, 2026-10-03

- 19 tests passed: component downloads (11), existing picker (1), CUDA import (2),
  thin package (5), under development Python 3.12.14. The package test builds a
  temporary artifact with fixture runtimes and checks downloader entry hashes;
  this is not an executable release package.
- 11 existing CTranslate2 component tests passed under isolated official embedded
  CPython 3.11.9. Initial execution under 3.12 correctly hit the importer ABI
  guard (three test failures); rerun under the required ABI passed. No ABI guard
  or existing tests were weakened.
- New downloader fetched the real pinned model `config.json` (2,394 bytes) from
  Hugging Face over HTTPS and verified the committed SHA-256. No model weights
  or CUDA binaries were downloaded for this validation.
- No production/Beta installation, integration tasks, or real user data used.

Targeted test commands from the source checkout (runtime paths are developer
inputs, not product dependencies):

```
<dev-python-with-Tk> -B -c "import sys,unittest; sys.path.insert(0,'tests'); r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromNames(['test_component_downloads','test_component_picker','test_cuda_import_flow','test_thin_package'])); sys.exit(not r.wasSuccessful())"
<python311> -B -c "import sys,unittest; sys.path.insert(0,'tests'); r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromName('test_ctranslate2_component')); sys.exit(not r.wasSuccessful())"
```
