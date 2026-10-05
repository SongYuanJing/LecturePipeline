# Phase 2a published-release gate

Authorized scope: two public prereleases on SongYuanJing/LecturePipeline,
`v1.9.6-gate.1` (A) and `v1.9.6-gate.2` (B). These are qualification releases,
not a production recommendation. Both use the same application source; B changes
the packaged version to exercise the real update protocol without unrelated code.

A ships the rebuilt self-contained Setup.exe with the Phase 2a stable launcher,
plus its matching code-only update manifest/archive. Setup retains the existing
pinned v1.9.5-beta.1 private-base download; it embeds the new application payload.
B ships only its manifest and code archive. No main-branch update source is used.

The gate uses a new disposable installation and data root. Existing verified
supplier download cache may be reused after a normal Setup cancellation; no
installed runtime/model files are copied. Setup itself downloads the private base,
verifies/imports suppliers and creates fresh data. Setup and B's update archive
must be downloaded from their actual published GitHub release URLs.

The final record must distinguish supplier cache reuse from real network fetches,
and include window/version evidence, config/data hashes and mtimes, retained A,
and the final no-update result. Production/baseline/data roots remain untouched.
Phase 2b and all other roadmap work remain out of scope.

## Result: passed on 2026-10-05

Windows 11 x64 / RTX 3050 host. Published prereleases:

- [A: v1.9.6-gate.1](https://github.com/SongYuanJing/LecturePipeline/releases/tag/v1.9.6-gate.1)
- [B: v1.9.6-gate.2](https://github.com/SongYuanJing/LecturePipeline/releases/tag/v1.9.6-gate.2)

Both tags point to `2453e0a9205c9e15f2274532c122b8bd13544f3e`.
The branch was pushed without force after one successful push dry-run.
The pre-existing beta release was not changed, and neither gate release was
marked latest. They remain publicly available for reproducing this gate.

Evidence: [phase2a-remote-2026-10-05.json](phase2a-remote-2026-10-05.json).
Reproducible explicit harness: `tests/published_updater_gate.py`; no HTTP or
process mocks. Installed private Python executes the actual updater CLI, which
is the same entry point used by CheckUpdates.cmd/Update.cmd. The final
CheckUpdates.cmd itself was also invoked and returned no-update.

| Check | Measured result |
| --- | --- |
| Disposable root | `%TEMP%/LP2a-remote-20261005`, install `Программа 课程`, data `Данные 课程` |
| Setup from public A | 51,814,685 bytes; SHA-256 `412691c37781f6804d63414d5ca32466e73971577ffd04077dca69d2a5e7ccb5` |
| Private base | Actual GitHub download, 80,109,954 bytes; SHA-256 matched the existing base pin |
| Component cache | Nine verified cache hits; actual imports, no copied installed runtime/model |
| Component/runtime probe | Base, PyAV, CTranslate2, model and CUDA Valid; full Auto selection cuda/int8_float16 |
| A launch | Actual main window `Lecture Pipeline · 1.9.6-gate.1`; ready Setup report and shortcut created |
| Setup cycle | 283.531 s, including GUI confirmation/close and disposable Word fixture creation; excludes Setup download and cache preparation |
| Discovery | A returned no-update before B publication, then available `v1.9.6-gate.2` from the real Releases endpoint |
| B archive | Real network download, 101,933 bytes; SHA-256 `dfdff9dd8aefed2d5fdd10a167752fbce7143431380538b38ff091e1b61299fa` |
| Update | Verified manifest and ZIP, staged native health subprocess, atomic pointer switch, first GUI readiness; 21.297 s including apply metadata/network |
| B launch | Actual main window `Lecture Pipeline · 1.9.6-gate.2`; pointer now `versions/1.9.6-gate.2` |
| Data/config invariance | Exact SHA-256 and nanosecond mtime equality for config, vocabulary.xlsx, real Word fixture, state.json and ai_state.json |
| Retention | A remains; no pending update transaction |
| Final check/cache | no-update; verified update cache SHA/size/mtime unchanged by the check |

Both GUI processes were closed normally after confirming their versioned main
windows. No production/baseline/existing test data root was modified. No product
defect was found. The harness needed an explicit import path for the development
embedded Python; this did not change the product or published artifacts.
Eight targeted bootstrap tests passed during preparation; the real remote gate
then exercised the installed code. No unrelated regression suite or ASR lecture
was run for this update-only task.

Limits remain those of Phase 2a: compatible code-only updates, capable A base
required, unsigned artifacts, bounded health/GUI-start checks, no late-crash
monitoring, runtime migration or background updates. B intentionally changes
only the packaged version, not application behavior. Supplier network download
was not repeated here; prior native qualification plus verified cache reuse is
explicitly distinguished from the new real GitHub Setup/base/update downloads.
Phase 2b and other roadmap work were not started.
