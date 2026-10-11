# VIC-11 — authoritative lecture dates

Implemented and disposable acceptance-tested on 2026-10-11.
Starting branch `feature/course-setup-gui`, clean HEAD
`6e508fc4594452af4c2ef0a99f6a9d310f5b6bd1`. No release/version bump.

## Audit: before and after

| Path | Before | VIC-11 |
|---|---|---|
| human_ux.add_lecture | Required explicit day; GUI prefilled today | Shared resolver; GUI blank means filename inference; unresolved import refused before copies |
| Inbox source | First valid filename date; separate imported_at; recorded_at null | Shared filename parser; multiple conflicting hints remain unresolved; raw evidence retained |
| Multipart | Compared dates, then copied first member's value/source | Shared session resolver, per-member evidence, conflicts never majority-voted |
| READY | Optional intake dict, sealed with source signatures | Same contract; resolved additive fields carried unchanged |
| Raw manifest | Passed through READY intake | Same unchanged pass-through |
| Processing state | No date metadata | New completion records include resolved metadata; worker publication retains that record |
| AI queue | Date from key, optionally intake; packet task dropped provenance | Shared legacy reader; new packet task includes all date fields; manifest remains sealed |
| Word/finalizer | Completion date parsed from key; subtitle only key | Explicit authoritative date/source paragraph; completion entry receives same metadata |
| GUI review | Date correction before reservation only | Date/source visible; published save disabled with explanation; service guard remains authoritative |
| Output filenames | Key number + date | Same naming from resolved date; no import-date fallback, no automatic rename |

`source_modified_time` in the legacy Word packet and file signatures still use
mtime for integrity/change detection. They never supply lecture_date or
recorded_at. Identity continues using existing reservations and file signatures;
no dedup/catalog architecture changes.

## Additive contract, schema remains 1

The existing `intake` dictionary is authoritative for newly accepted sources and
sessions. `lecture_dates.py` is the only date parsing/resolution/legacy projection
module; there is no new storage or database.

- `lecture_date`: nullable date-only, strictly YYYY-MM-DD; calendar lecture date.
- `lecture_date_source`: filename / explicit / unknown; legacy for old values
  whose provenance was never recorded.
- `lecture_date_raw`: original filename token or explicit entered date, nullable.
- `imported_at`: offset-aware ISO timestamp; generated at source acceptance into
  Inbox (first discovery), not ASR completion. A session retains its earliest
  member acceptance; manual import captures its request timestamp. New manual
  and resolved values normalize to UTC. Review preserves this instant.
- `recorded_at`: optional exact recording start. New imports remain null under
  the current trust policy; no filesystem timestamp is substituted.
- `recorded_at_source`: unknown for new untrusted/absent values; legacy on read
  for older supplied timestamps without a source.
- `date_resolution`: resolved / unknown / conflict.
- `date_evidence`: filename tokens or per-member date/source/raw evidence,
  including members without hints; an override retains the prior evidence.
- `date_override`: true for explicit selection/correction; false for inference.

READY -> raw manifest -> completion state -> new AI packet task -> Word and
AI completion entry carry this metadata. AI instructions explicitly forbid
guessing/replacing dates from transcript or import time.

## Priority and multipart membership

1. Explicit user/session override.
2. Agreed valid filename hints.
3. Unknown/conflict -> review (no trusted embedded fallback is enabled).

Conflicting explicit inputs also remain unresolved. No majority vote. Multiple
different valid dates in one filename are ambiguous. Invalid date tokens are not
accepted as calendar dates. Date-only values are never shifted by timezone.

A missing member hint can inherit an agreed date only when existing grouping
already establishes the same normalized session. Per-member unknown evidence is
kept. This resolver never joins differently named sessions. Since the current
stem includes its date text, files differing by omitted date commonly remain
separate; no speculative cross-stem merge was added. Manual selection without an
explicit date conservatively requires all selected files to have agreeing hints,
because selecting files alone does not prove common session membership.

## Correction and identity

Before reservation, GUI correction updates the existing Inbox row/group in one
journal write, sets explicit provenance, resets stability, and preserves
imported_at. It does not invent a second lecture identity. The original source
files remain untouched.

After key reservation/READY/publication, date changes are blocked. GUI explains
that a separate safe rename/migration operation is required; that operation is
not implemented here. Backend independently rejects the edit. Completed output,
key, AI packet and Word are never silently renamed, rewritten or requeued.
This is the explicit conservative policy allowed by VIC-11's identity rule.

Unknown automatic dates remain review without READY. Unknown manual imports
return a validation message before copying files. Thus no new unknown filename
marker is necessary and legacy key grammar remains compatible.

## Embedded metadata audit and trust decision

Read-only PyAV 18.1.0 audit of the authorized real test M4A samples found:

| Source filename date | Embedded creation_time (UTC) |
|---|---|
| 2026-09-16 | 2026-09-20T23:11:08.000000Z |
| 2026-09-18 | 2026-09-19T18:45:27.000000Z |
| 2026-09-21 | 2026-09-21T10:06:50.000000Z |

Container and audio-stream values agreed; Core Media Audio handler was present.
That does not authenticate iPhone recording provenance. No verified original vs
exported iPhone pair was available, so preservation through iPhone export is not
claimed. Read-only audit checked source size/mtime unchanged. The existing small
WAV had no container/stream metadata.

Apple defines QuickTime movie-header creation time as movie-atom creation,
with UTC preferred, not a guarantee of recording start:
[Apple creation time](https://developer.apple.com/documentation/quicktime-file-format/movie_header_atom/creation_time).
PyAV exposes container metadata through its existing API:
[PyAV containers](https://pyav.org/docs/stable/api/container.html).

`scripts/vic11_metadata_formats.py` encoded tiny disposable files using current
PyAV for all nine accepted extensions. Deliberately unrelated date/creation tags
survived as follows (this is evidence of writable tags, not trust):

| Formats | Observed metadata location |
|---|---|
| M4A / MP4 / MOV | Container date and creation_time; stream creation_time |
| WAV | Container date; creation_time absent |
| MP3 | Container date and creation_time |
| AAC/ADTS | No retained date tags in this fixture |
| FLAC | Container date and creation_time |
| OGG / OPUS | Audio-stream date and creation_time; empty container metadata |

Therefore none of these generic tags automatically supplies recorded_at or
lecture_date. No media parsing dependency was added to normal ingestion.
Audit scripts are optional developer tools using existing private PyAV.
Trusted embedded-time test J is intentionally not applicable: no trusted source
is enabled. UTC/offset normalization is tested independently. Explicit
recorded_at entry UI is not introduced in this scope.

## Backward compatibility

Absent intake/fields remain readable without writing them on load. A date from
an old key or old lecture_date is exposed as legacy, never falsely filename or
explicit. Missing import/recording timestamps stay null. An explicit null date
in intake wins over a date-looking key. Existing sealed AI packets and completed
outputs are not regenerated simply to add fields. Legacy output_folder mapping,
split destinations and manual imports are covered by regression.

## Verification

- 88 tests passed in 49.122 s: dates (12 new), single-file Inbox, multipart,
  course setup/review GUI, DPI, human UX and local finalizer.
- Final affected run: 35 passed in 10.535 s (12 dates + 4 real Tk course GUI +
  19 worker tests). This followed a small fix preventing the same source override
  from being applied twice and losing the original unknown evidence.
- Total distinct relevant tests: **107**, not the sum of repeated runs.
- The first gate harness lacked an unused refresh callback; corrected before
  acceptance. No product failure was concealed.

Final native gate: `%TEMP%/LP-vic11-rqp25mwq`, `evidence.json` retained.
Media format audit: `%TEMP%/LP-vic11-media-y5ogqgf4/evidence.json`.
Reproducible scripts and compact sanitized evidence are stored in this repo.

Native gate used real Windows filesystem, valid generated WAVs, real elapsed
time (10 s settle / 5 s poll only in disposable config), Tk 200% scaling and
actual review Entry/Button callback, fresh Inbox/Tk reopen, READY and raw
publication, AI packet creation, actual Word finalizer and state updates.
Whisper transcript and external AI content were fixtures. No scheduler service,
OS mouse automation, new ASR qualification or full installed-main-GUI launch is
claimed; the existing GUI component and processing services were exercised.

Eight acceptance checks passed: yesterday imported today; unknown review;
consistent multipart; conflicting multipart; GUI correction; reopen retention;
published edit blocked/no duplicate; identical raw/AI/Word metadata.
Three lectures completed: 01_2026-10-10, 02_2026-10-10, 03_2026-10-09.
Original/config hashes and mtimes unchanged; sealed READY/raw/Word files unchanged
after reopen. Application-controlled date 10 Oct differs from actual import
11 Oct; generated source mtime was deliberately set near the Unix epoch.

Protected production, baseline, working Beta and university data were not
modified. Existing authorized Drive test samples were read-only; all newly
generated audio/runtime evidence was in disposable Temp. No release/tag/push,
updater architecture or next roadmap phase.
