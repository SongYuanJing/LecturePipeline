# Phase 1b — device selection and persistence

Implementation commit: `bd77226843705a481999c64dcf1516dc44cc4c41`.
Branch: `feature/bootstrap-downloads`. Validation date: 2026-10-03.

Status: implementation and controlled disposable process smoke complete. This is
not native supplier qualification and not a release candidate. Phase 1c has not
started; its fresh-Windows executable architecture requires a separate decision.

## Contracts

Config remains schema 1. New authoritative optional field:

```json
"asr": {
  "model": "large-v3",
  "device_mode": "auto",
  "preferred_device": "cpu"
}
```

`device_mode` accepts `auto`, `cpu`, `gpu` (UI: Auto, CPU, GPU). It is the user's
policy, not a persisted hardware-capability claim. Unknown values, including an
explicit null, fail validation. No config migration or rewrite occurs on load.

| Input | Effective policy |
| --- | --- |
| New `auto` | GPU only after successful component + private-runtime inference probe; otherwise CPU if its runtime is available |
| New `cpu` | CPU int8, no VAD, no CUDA requirement/download/probe |
| New `gpu` | CUDA int8_float16; failed probe blocks with reason and CPU/Auto suggestion; later CUDA failure does not retry on CPU |
| No new field, old `preferred_device=cpu` | CPU |
| No new field, old `preferred_device=gpu` | Auto (preserves old fallback behavior) |
| Neither field present | Auto |

First-run persists `device_mode` plus legacy `preferred_device=cpu/gpu` reflecting
the selected backend at setup. New code always gives `device_mode` priority.
Older binaries ignore the new field and retain their old fallback semantics;
strict GPU is a new-code contract, not a promise about running an old binary.
Changing mode in an existing config requires stopping/restarting workers. This
slice adds the selector to first-run, not a new application-wide Settings editor.
CLI first-run accepts `Setup.cmd --device-mode auto|cpu|gpu`.

## Detection and execution

- Windows video-controller names are informational. Inventory failure is shown
  as unknown, not interpreted as proof of GPU absence or success.
- Packaged installations reuse base/component SHA-256 checks. CPU mode skips
  CUDA component validation. Legacy layouts without component manifests use the
  runtime probe; this does not retrofit supplier hash verification to legacy data.
- Probes invoke the configured private Python with isolated paths and offline HF
  cache. Python and ASR modules must belong to the application directory.
- CPU probe checks imports and int8 capability; it does not preload the 3 GB model.
- GPU probe runs in a separate process: device count, VAD execution, local CUDA
  DLL load, large-v3 load, one-second synthetic WAV decoding and consumed inference
  generator. VAD is tested separately; inference disables VAD so silence cannot
  skip GPU execution. Returned actual backend must be CUDA.
- CPU/GPU probes have 60/180-second limits. GPU native crash, timeout, load failure
  or incorrect response never grants GPU availability. CPU result is independent.
- Selection is cached only in a Config instance, not saved as permanent readiness.
  Model construction and preflight share the same policy; both lecture and dialogue
  already use `Config.new_model`. Auto retains the existing sticky runtime CPU
  fallback; explicit GPU disables it. Child results now include `actual_device`.
- Quick Components status uses `Unverified` for present CUDA until a full probe;
  a GPU count or DLL presence alone is no longer labelled available.

The inference/VAD calls follow the pinned faster-whisper 1.2.1 interfaces:
[transcribe](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/transcribe.py),
[VAD](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/vad.py).

## Changed files

| Files | Purpose |
| --- | --- |
| `src/app/asr_device.py` (new) | Policy, inventory, component gate, isolated probes |
| `src/app/pipeline_config.py` | Compatible config loading, shared selection, preflight |
| `src/app/lecture_asr.py` | Explicit fallback control and actual-device assertion/report |
| `installer/asr_devices.py` (new) | First-run bridge to selected release/private runtime |
| `installer/setup.py`, `config.example.json` | Validate before writes, persist mode, CLI option |
| `installer/setup_gui.py` | Hardware/recommendation, user selection, separate setup/components tabs |
| `installer/component_status.py` | Distinguish basic availability from full GPU readiness |
| `tests/test_asr_devices.py` (new) | Policy, failures, compatibility, persistence, GPU probe/ASR contract |
| `tests/test_device_smoke.py` (new) | Real private-Python subprocess routing with explicit fake suppliers |
| `tests/test_ctranslate2_component.py` | Updated quick-status expectation; no inferred GPU success |
| `ARCHITECTURE.md`, `docs/NEXT_PHASES.md`, this document | Current contract, delivery state and evidence |

## Validation

119 distinct tests passed across the affected execution paths:

- 21 new device-policy/config/setup/probe tests plus 1 disposable process smoke.
- 86 existing ASR, worker, lecture pipeline, dialogue, first-run prerequisite,
  download, picker, CUDA import and thin-package tests (Python 3.12.14).
- 11 CTranslate2 component tests on isolated Python 3.11.9.

After final code adjustments, the 22 new tests and 15 existing ASR tests were
rerun together (37 passed), as were the 11 CTranslate2 tests. Tests do not install
tasks or touch production/Beta/test data roots. No push attempted in this phase.

The process smoke copies an explicitly supplied embedded Python into a temporary
application, adds clearly labelled fake supplier modules/model/audio, persists
CPU/Auto/GPU, and invokes the real Config -> probe -> ProductionWhisperModel ->
ASR child path. CPU and Auto produced CPU/int8/no-VAD backend evidence without a
CUDA directory. Forced GPU produced no CPU output and explained CPU/Auto recovery.
The GPU unit fixture executes the real probe/child code with substituted native
dependencies; it is not a real CUDA measurement.

Reproduce the short process smoke from the checkout:

```powershell
$env:LP_TEST_PYTHON311 = '<isolated embedded Python 3.11>/python.exe'
& '<development Python>' -B -m unittest discover -s tests -p test_device_smoke.py -v
```

## Remaining gates and limits

- Phase 1a is implementation-complete, not release-ready: full pinned supplier
  download/import and private native runtime integration remain open.
- Phase 1b routing/behavior is tested. Actual pinned large-v3 CPU/GPU execution,
  VAD and driver/native compatibility must still be qualified in a disposable
  candidate with real suppliers before release. The current smoke cannot certify
  that stack, real GPU performance, or first-run visual layout on all DPI settings.
- A successful short GPU probe cannot guarantee enough VRAM for every subsequent
  lecture. Strict GPU surfaces later errors; Auto can fall back as before.
- Cold model probing/hash reads add startup/setup time. Slow hardware may reach
  the conservative timeout and Auto then chooses CPU. No persistent readiness
  cache or timeout tuning UI is added in this slice.
- Phase 1c is explicitly paused pending the owner's bootstrap-executable decision.

All new commits remain local. After GitHub write access is restored, push the
whole `feature/bootstrap-downloads` branch (including the earlier 1a commits);
do not force-push, merge main or publish a tag as part of that operation.
