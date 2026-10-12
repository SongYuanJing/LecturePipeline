# VIC-14 progress observations

## Pre-implementation audit (2026-10-11)

Starting HEAD: 052585d08e0444a3153616864ea49e0608882ae5.
Worker seals/verifies READY inputs, processes ordered local copies, commits a local
raw bundle and publication plan, publishes raw/state, then the existing AI queue
and finalizer own the remaining transitions. These boundaries stay unchanged.

ProductionWhisperModel runs faster-whisper in a private subprocess. The generator
is fully consumed there; the pipeline receives a materialized iterator afterwards.
Instrumenting only that outer iterator would report progress after inference, not
during it. The child already reports original segment end timestamps and info.duration
at most once per second. Parent polls once per second. Existing progress is a single
asr_progress.json and a per-part human_ux estimate; neither is lecture-weighted.

worker_jobs is recovery authority; worker_status is atomic heartbeat observation
and also mirrored to Drive. New progress must be local-only, keyed by lecture,
not included in the Drive mirror. Heartbeat runs every 60 seconds. GUI snapshots
run on a background thread every 3 seconds. Catalog is a read-only projection with
durable completion precedence. Its unchanged-render shortcut must remain; changing
progress also needs incremental row updates to retain selection/details scrolling.

Duration policy: inspect PyAV audio-stream/container metadata once on verified
local copies, without decoding or changing READY/manifests. Unknown duration means
unknown aggregate percentage until actual recognizer durations are available.
Within-part timestamps are observations of the consumed source timeline, not a
claim that silence/gaps took proportional compute time. No progress/ETA for opaque AI.

## Implementation contract

Implementation commit: `560f0fa6e128de6fbfc15a2530f82848db192f3e` on
`feature/course-setup-gui`. No version/schema migration or release change.

`worker_status.json.lectures[course/key].progress` is an additive local observation:
schema, identity/course_id/lecture_key, attempt UUID, stage, active, part_index,
part_count, processed_audio_seconds, total_audio_seconds, percent, elapsed_seconds,
eta_seconds, eta_available, updated_at, backend, worker_started_at and job_token.
No new database/journal. No fields are added to READY/raw/AI/completion authorities.
Worker recovery still uses its original job token/phase and committed bundles.
The Drive status mirror explicitly strips progress; no per-segment Drive writes.

N is the index of the current verified ordered copy; M is the length of that
READY-validated list. No source-folder counting or part reordering. When inactive,
the catalog retains its static member count and has no invented current N.

Duration is positive finite PyAV audio-stream duration × time_base, falling back
to container duration when unavailable. Metadata is read once per verified local
part. Actual faster-whisper info.duration supersedes metadata for that part.
Invalid/missing/zero duration is unknown, never a fabricated zero duration.
The installed faster-whisper 1.2.1 source was inspected: duration is measured before
VAD; restore_speech_timestamps restores yielded segments to source coordinates.
No recognizer internals were patched. Child segment collection/output is unchanged.

For known durations d[1..M], current part i and observed source end t:

```
processed = sum(d[:i-1]) + clamp(max_observed_t, 0, d[i])
total = sum(d)
percent = 100 * clamp(processed / total, 0, 1)
```

Any unknown duration hides aggregate percentage/ETA, while N/M remains visible.
For 60+5 minute parts, completed first part is 92.31%, not 50%.
Generator exhaustion completes the source timeline; publication immediately hides
percentage/ETA. Raw commit overrides any old ASR observation. AI wait, Word building
and final Done use the existing catalog resolver, without made-up percentages.

## ETA and cadence

ETA means remaining **ASR** time for this lecture, not time until Word. It uses
observed source seconds per wall second, with EMA speed:

```
sample_speed = max(0, delta_source_seconds / delta_wall_seconds)
alpha = 1 - exp(-delta_wall_seconds / 30)
speed = speed + alpha * (sample_speed - speed)
eta = (total - processed) / speed
```

Samples update at intervals >=1 s. First sample initializes speed. ETA requires
>=20 s of ASR observation, >=30 newly observed source seconds, >=5% aggregate
progress, positive finite speed and a source advance within the last 15 s.
At completion, unknown measurement, or a stall, ETA is hidden. UI rounds a valid
estimate up to approximate whole minutes; otherwise says "рассчитывается…".
History resets for each new part/child/session or device fallback; completed source
durations still contribute to percentage. Conservative per-part warmup can hide ETA
for short parts. No extrapolation across different machines or persisted history.

Parent observation writes are limited to once per second, except explicit part/end/
publication transitions. Child already throttles its private progress file. Existing
60 s worker heartbeat remains. GUI background polling remains 3 s; it neither opens
media nor hashes source files. Catalog snapshot is reused by dashboard (no duplicate
scan or second percentage calculator). Multiple identities remain separate; the
dashboard does not combine independent lectures into a fictitious global percent.

Live observations require running worker, matching start/session and job identity,
heartbeat age <=90 s, observation age <=10 s, matching part count and finite values.
On crash/restart stale percentage/ETA disappears; durable stage labels remain the
catalog's labels. Retried ASR starts fresh, not at a recovered partial percentage.
Read/write telemetry failures cannot fail successful ASR; damaged child telemetry
also cannot prevent existing CUDA error/fallback classification.

Catalog's unchanged-render shortcut is retained. Changed progress updates existing
rows without deleting/reselecting them; details retain scroll and selected identity.
One compact Progress ASR column is scrollable at narrow widths. Full details use
the same presentation model as the main dashboard. Legacy states with no progress
remain valid and display their existing durable stage without a live percent/ETA.

## Acceptance (2026-10-12): PASS

- 236 distinct relevant tests passed. Main affected batch: 207 actual cases passed
  in 69.870 s (the invocation also listed two nonexistent test modules; these were
  harness name errors, not product failures). Additional real suites: 27 passed
  in 4.304 s. Final affected reruns: 40 in 4.253 s and 16 ASR in 0.150 s, adding
  two unique cases. Covers Inbox, multipart, course GUI/DPI, dates, recovery,
  catalog, manual import, worker/raw, AI/finalizer, dialogue and legacy states.
- Real ASR: `%TEMP%/LP-vic14-asr-lvs9ohcg/evidence.json`. Existing disposable
  Phase 1c private runtime/model reused read-only; no download. RTX 3050 CUDA,
  large-v3, int8_float16, VAD; synthetic English WAV 36.99325 s. Five segments;
  instrumented SRT byte-identical to baseline and committed raw verified. Timeline
  moved 0 -> 7.84 -> 36.99325 s. Metadata 36.993197 s. ETA correctly absent on this
  short run. Baseline wall 26.442 s; instrumented 14.760 s (warmup differs, so this
  comparison does NOT measure overhead). Recorded tracker elapsed also includes
  baseline setup in this first harness run; future harness creates it afterwards.
- GUI visual: `%TEMP%/LP-vic14-gui-65z19e3v/evidence.json` plus interactive tool
  observations: real CatalogPanel and dashboard at 192 DPI/200%, narrow and
  maximized, Russian/Chinese names, 3/8 with percent/ETA, 1/1 with ETA calculating,
  AI pending and Done with no live progress. Selected row/detail scrolling survived
  background refresh. No product layout fix was needed after the progress column.
- That first harness's overly broad file-set comparison included the empty GUI
  startup log and failed. Corrected invariance gate:
  `%TEMP%/LP-vic14-gui-ezc4767a/evidence.json`, PASS, changed_files=[], no callback
  errors. Only the exact GUI runtime log and intentionally updated worker_status
  are excluded; config, media, READY/raw, jobs and AI records are compared by
  SHA-256/mtime. Visual evidence is reused because product layout was unchanged.
- Performance: `%TEMP%/LP-vic14-overhead-nhu6q3_x/evidence.json`. 100,000 callbacks
  over 99.999 simulated seconds -> 100 real atomic writes, min interval 1 s;
  wall 0.577 s, CPU 0.438 s, atomic writes 0.337 s. This measures local observation
  cost, not a long real-ASR CPU benchmark. Four-row live catalog build 10.52 ms;
  existing 300-entity regression build 3.156 s. No recurring media reads/hashes.

## Limits and protected scope

Segment timestamps can jump over VAD silence; ETA is an approximate ASR estimate,
not a smooth promise. Metadata may be corrected by decoded duration. Short parts
can finish before enough ETA evidence exists. Native qualification used one short
GPU recording, not a two-hour performance/quality study; CPU/fallback semantics and
ETA timing were covered deterministically. GUI worker/progress/Scheduler were
fixtures; real ASR qualification was separate and did not substitute native modules.

Production `C:\WhisperLocal`, baseline `C:\PipeLine`, working Beta, real university/
study/Google Drive files were not used or changed. Writes stayed in the repository
and explicit disposable Temp roots. Published tags/releases, updater architecture
and global settings untouched. No push, release/version bump, VIC-15 or other phase.
