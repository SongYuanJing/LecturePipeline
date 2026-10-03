# Portable package contract — v1.9.5-beta.1 thin Beta

Development after this baseline: [phased plan](docs/NEXT_PHASES.md) and
[online component download slice](docs/ONLINE_COMPONENTS.md). The contract below
describes the released Beta; the new source has not been published as that tag.

## Choice and layout

The first offline candidate is a standard ZIP built with Python stdlib, not a monolithic EXE or an installer framework. This minimizes new dependencies and allows component updates. Extract anywhere writable by the current Windows user. No administrator requirement.

```
Application/
  current.json, package-manifest.json, *.cmd, Lecture Pipeline.vbs
  launcher/                 stable bootstrap/control entry points
  versions/1.9.5-beta.1/  code + release.json + migrations contract
  runtime/asr/              private CPython 3.11.9 + base dependencies + Tk
  runtime/document/         private CPython 3.12.14 + docx/openpyxl/lxml
  runtime/components/       externally imported PyAV and CTranslate2 (not in ZIP)
  runtime/cuda/v1.3/         optional imported CUDA DLLs
  models/huggingface/hub/    verified offline large-v3, shared by versions
  config/config.json        first-run output, never in Git or archive
  logs/, run/, backups/     mutable local data, never under versions
ExternalData/
  <workspace>/<subject>/{audio,raw,word}
  <workspace>/system/{state.json,ai_state.json}
  dialogue/, dictionary/vocabulary.xlsx
```

Two private Python versions deliberately retain the proven binary environments. `_pth` disables registry/environment/user-site dependencies; `launcher/sitecustomize.py` exposes only the selected application modules. Neither system Python nor Codex is required. Full private CPython includes Tk; the official embedded distribution omits Tcl/Tk ([Python Windows documentation](https://docs.python.org/3.11/using/windows.html)). Runtime builders take explicit donor directories; no personal donor paths appear in generated manifests. Exact current locks and observed versions are in `components/`.

`build_runtime.py` clones explicit local CPython inputs and selected dependency packages, records SHA256. `build_package.py` verifies runtime manifests, stages source/launcher, emits per-file release/package checksums and a ZIP with stable timestamps. Builds are reproducible from the same verified component inputs (source-independent absolute paths are excluded). Source does not contain runtime binaries. Creating the CPython inputs from public distributions/wheels must be validated on a clean machine before public release.

Example build parameters (placeholders; no implicit system Python):
```
<build-python> scripts/build_runtime.py --asr-base <CPython311> --asr-site <locked-site-packages> --document-base <CPython312> --out <components/runtime>
<build-python> scripts/build_package.py --components <components/runtime> --out <new-output-root>
```

## Model and GPU

Chosen beta contract: offline import, not download. Model identity `Systran/faster-whisper-large-v3`, revision and five SHA256 values are pinned in `components/model-manifest.json` (~3.09 GB). The app-owned HF-format cache retains unchanged ASR loading semantics. Import verifies source and copied files; an existing matching model is reused. Invalid or partial components fail rather than overwrite. Remove/review an abandoned `.pending` directory explicitly before retry. No network required. Components/bootstrap verifies pinned component hashes before setup/launch; application preflight also checks model structure. Hash verification adds startup I/O.

Optional CUDA v1.3 component (~1.78 GB) pins cuBLAS 12.9.2.10 / cuDNN 9.10.2.21. DLL paths are injected in the ASR child only. No global PATH/driver changes. Windows x64, compatible NVIDIA driver/hardware needed for GPU; CPU int8 remains fallback. No RTX-model assumption. Preflight capability report is a probe, actual load can still trigger the existing safe fallback. Verify drivers/native dependencies on the next clean machine. Current package is not a driver installer.

## Integration, uninstall, updates

Integration plans then explicitly registers user logon tasks with an installation-specific UUID prefix, private pythonw and stable launcher. Existing task collisions fail. Scope uses Windows [user logon task semantics](https://learn.microsoft.com/en-us/windows/win32/taskschd/logon-trigger-example--scripting-). It does not register, stop or replace production tasks. App-root shortcut avoids desktop/Start menu assumptions.

Close the candidate GUI and stop candidate workers gracefully. Run `launcher/RemoveIntegration.ps1` to review, then `-Apply`. `Uninstall.cmd` previews immutable hash-owned files; `Uninstall.cmd -Apply` removes only those exact files using Windows PowerShell (not the Python being deleted). It refuses changed files or remaining integration marker. Config, models, imported PyAV/CTranslate2, optional CUDA, logs/run/backups, external user data and the manifest are preserved. Empty directories may remain; this is intentional. No recursive user-data deletion. Do not manually remove the integration marker to bypass checks.

Manifest versions: app `1.9.5-beta.1`; config schema 1; lecture/dialogue/AI schema 1; dictionary 1.4. No data migration. `versions/.../migrations/README.md` defines future migration contract. Candidate rollback: uninstall candidate integration/code only; production v1.8.1 is untouched. Source rollback via local Git tag `v1.8.1` is a developer operation, not a user-data restore. Keep model/runtime outside version directories.

## External components and distribution gate

The public ZIP excludes the complete CTranslate2 supplier closure (including Intel OpenMP/static native pieces), PyAV/FFmpeg/codecs, Whisper model, CUDA/cuBLAS/cuDNN and all user data. Import exact supplier wheels separately using [Offline installation](docs/OFFLINE_INSTALL.md). The whole CTranslate2 wheel is imported locally; no DLL is pruned. Ownership/path/native exclusion checks fail a contaminated build.

The remaining base inventory lists 29 package entries, 143 native files and 99 license texts. Their existing package/incorporated-software notices remain included. External supplier technical manifests are not a legal-clearance claim and do not authorize mirroring their binaries. See THIRD_PARTY_NOTICES.md.

Microsoft Word is optional for generation (python-docx), useful for viewing/editing. Google Drive Desktop is optional: an available local filesystem data root is supported. Windows PowerShell, Task Scheduler and Explorer are integration dependencies. Microsoft VC v14 x64 is an explicit prerequisite obtained directly from Microsoft, never installed automatically. Hashes detect corruption, not publisher identity.

Plan C technical results are in docs/PLAN_C_VALIDATION.md. Historical deployment evidence is retained. This Beta pass validates one new disposable installation on the same host; it does not certify a freshly provisioned Windows VM or repeat login/reboot/uninstall. See docs/BETA1_VALIDATION.md. Production is not a test target.

Local finalize is an explicit private-document-Python command; see docs/LOCAL_AI_FINALIZE.md. It does not require Codex/Work or a network connection.
