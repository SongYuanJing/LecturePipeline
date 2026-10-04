# Post-beta development plan

Baseline: `47d73cf`, tag `v1.9.5-beta.1`. Branch: `feature/bootstrap-downloads`.
The owner reports a clean-install happy path through Word and dictionary. That
does not certify a clean Windows VM, reboot/uninstall, or update recovery.

## Boundaries

- Develop in an independent source checkout. Do not modify production, the tested
  Beta, or its data root. All mutation tests use temporary disposable directories.
- Preserve schema-1 lecture/dialogue/AI/config and dictionary 1.4. No implicit
  adoption, migration, reprocessing, or replacement of user files.
- Commit reviewable slices with targeted tests. No release publication until a
  candidate passes its applicable gate. Release feeds use tags, never `main`.

## Audit of actual source

- `installer/launch.py` validates `current.json`, version hashes and config/code
  agreement. `ARCHITECTURE.md` describes updates; there is no updater implementation.
- Four component manifests already pin PyAV 18.1.0, CTranslate2 4.8.2, large-v3
  revision and CUDA supplier wheels/DLL hashes. Existing importers stage and verify
  components. GUI exposes manual selection only. CUDA input is already an explicit
  text path in this source; the reported picker issue must not be assumed unfixed.
- `build_runtime.py` still needs donor Python installations; `build_package.py`
  packages private runtimes. This is not yet a reproducible online bootstrapper.
- `component_status.py` probes CPU/GPU capability; `pipeline_config.py` supports
  preferred CPU/GPU. First-run UI does not expose this choice. A detected NVIDIA
  device alone is not proof that the complete model/native stack will load.
- `Integrate.ps1` creates installation-specific tasks and an app-root shortcut,
  not Desktop/Start entries. Worker startup and Windows integration are distinct.
- `lecture_worker.py` has hash-based file checks for existing lecture processing.
  Arbitrary inbox ingestion still needs a separate stable-file/import contract.
- GUI adapter already combines state and has measured ETA helpers, but some rows
  explicitly lack part counters/current-task timing. Extend existing readers and
  worker events; do not create a competing processing database casually.
- Dictionary merge and local finalize exist. Vocabulary discoverability/export
  remains a UX issue; do not replace the workbook schema.

## Sequence and acceptance gates

| Phase | Scope | Done when |
| --- | --- | --- |
| 1a | Download pinned components through existing importers; reuse verified cache; retain offline import | GUI/CLI can obtain PyAV, CTranslate2, model and optional CUDA from suppliers; corrupt/interrupted download is never imported; retry reuses verified files; temporary-data tests pass |
| 1b | Hardware detection, explicit auto/CPU/GPU choice, first-run persistence | CPU needs no CUDA; GPU recommendation is backed by private-runtime probe; unavailable GPU has a clear CPU path; short disposable CPU/GPU smoke verifies config reaches ASR |
| 1c | Reproducible private Python/Tk/base dependencies and small bootstrapper | Fresh Windows profile without system Python or donor installs reaches working app; all downloaded artifacts pinned and verified; no global PATH/driver changes; package sizes and cache/disk needs shown; retry/cancel tested |
| 2 | GitHub Releases updater | Explicit stable/beta channel; approved manifest/authenticity design; stage side-by-side; stopped-worker guard; runtime/launcher compatibility; health check; guarded config/current switch; injected failures restore old version and preserve data |
| 3 | Desktop and Start shortcuts | Per-user, stable launcher target, spaces supported, ownership-aware removal; independent of worker tasks; no collision with another installation |
| 4 | Inbox / Google Drive Desktop local folder | Explicit workspace/subject and lecture grouping; stable readable files only; hash dedup survives restart; partial/offline files retried; recorded_at may be unknown, imported_at is ingestion time, lecture_date is explicit/inferred with provenance; legacy data unchanged |
| 5 | Unified catalog, N/M, ETA | One view of existing lecture identities; worker publishes part progress; restarts/failures visible; ETA based on measurements and clearly unknown when insufficient; no duplicate processing authority |
| 6 | RU/EN settings | UI language and output language separate from ASR input language; persisted defaults; existing configs load; manual AI packet and Word honor output choice |
| 7 | Vocabulary view | Users can locate/open workbook, inspect additions and understand export/update; manual fields preserved; locked workbook gives actionable error |
| 8 | Optional AI API | Explicit opt-in provider/cost controls; secrets outside repo; validated identical output contract; retry/idempotency; manual ChatGPT remains available |
| 9 | Licensing decision, separate from implementation | Threat model and distribution/access policy documented; compare private distribution with signed offline licenses; acknowledge offline revocation limits; no shared embedded secret; updates/recovery remain usable; no server introduced implicitly |

Phases 2–9 are authorized roadmap work, not part of the first bootstrap commit.
Licensing is a design decision, not a blocker for component download work.

## First-slice limitations and next work

Phase 1a is the starting implementation, not completion of phase 1. Runtime
bootstrapping and CPU/GPU selection remain separate commits. Keep current package
version until a release candidate is intentionally prepared; do not overwrite or
publish another binary under the existing beta tag.

Download tests use tiny fixtures and simulated network failures. A real supplier
and private-runtime integration test is required before calling 1a release-ready.
The full multi-GB model/CUDA download is not part of every unit-test run.

Current handoff: phases 1a/1b are implementation-complete and native-qualified
on the Windows 11 / RTX 3050 host, including real supplier downloads, verified
cache/import and CPU/Auto/GPU inference; see [NATIVE_GATE.md](NATIVE_GATE.md).
This is not general release readiness or fresh-Windows certification. Earlier
contracts/tests remain in [ONLINE_COMPONENTS.md](ONLINE_COMPONENTS.md) and
[PHASE_1B.md](PHASE_1B.md). The owner selected a self-contained .NET 10 x64
WinForms pre-Python shell for Phase 1c, with Windows 11 x64 as the initial target.
Phase 1c is implementation-complete and native-qualified on this Windows 11 /
RTX 3050 host, including real HTTP resume, GUI, ASR, warm rerun and shortcut.
Implementation and native acceptance evidence are tracked in
[PHASE_1C.md](PHASE_1C.md). Stop after Phase 1c; Phase 2 requires a separate
instruction. Continue locally while GitHub write is blocked.
