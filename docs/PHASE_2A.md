# Phase 2a — manual tagged Releases updater

Status: implemented and acceptance-tested on Windows 11 x64, 2026-10-05.
Stop after this slice. Phase 2b, automatic checks, signing infrastructure,
licensing, Inbox, runtime upgrades and data migrations are not implemented.
No production tag/release was created or changed.

## User entry points

Packages built from this source contain:

```bat
CheckUpdates.cmd
rem Close the main GUI and stop this installation's workers before applying.
Update.cmd v<version-reported-by-check>
```

The same installed private-Python commands are:

```bat
runtime\asr\python.exe -B -X utf8 launcher\updater.py check
runtime\asr\python.exe -B -X utf8 launcher\updater.py apply --tag v<version>
runtime\asr\python.exe -B -X utf8 launcher\updater.py recover
```

The manual command is the Phase 2a entry point; no background task or additional
GUI update panel was introduced. A successful update opens the new main GUI.
Failures leave/restore the previous pointer; the previous application can be
launched normally. Workers are never force-stopped or automatically restarted.

## Release contract and trust

Discovery uses only HTTPS GET
`https://api.github.com/repos/SongYuanJing/LecturePipeline/releases`, including
bounded pagination (at most 500 entries; exhaustion fails rather than returning
an incomplete comparison). Drafts and non-version tags are ignored. Ordering
uses numeric version and prerelease identifiers, not lexical string ordering.
A stable installation discovers stable releases; a prerelease installation can
discover newer prereleases and stable releases. `main`, source ZIP endpoints and
`target_commitish` are never update sources.

The [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
supplies the uploaded asset URL, exact size and `sha256:` digest. A candidate
must contain `LecturePipeline-update.json` with a GitHub SHA-256 digest. That
manifest is downloaded through the existing verified downloader and binds:

- `schema_version: 1`, exact `repository`, `tag`, `app_version`, `platform: win-x64`;
- `updater_protocol: 1`, `config_schema_version: 1`, `migration_required: false`;
- `runtime_contract`: exact SHA-256 of both private runtime inventories and the
  four installed component requirement manifests;
- `artifact: {name, bytes, sha256}` matching the same tagged Release's uploaded
  asset metadata and repository download URL.

Missing digest/manifest, invalid JSON/schema, wrong repository/tag, incompatible
runtime, bad size/hash or non-ZIP data fail closed. This trusts the official
GitHub repository and HTTPS metadata; SHA-256 is integrity verification, **not an
independent publisher signature**. No signing infrastructure was added.

`scripts/build_update.py --base <compatible-private-base> --out <new-output>
--version <approved-version>` builds these artifacts locally. It does not publish,
tag, change the repository VERSION, or embed runtime/model/user data in the ZIP.
The nested `release.json` retains the existing file inventory and adds
`updater_protocol: 1`; every version file and the complete archive are verified.

## Download, stage and transaction contracts

- `download_components.fetch(..., expected_size=..., resume=True)` opts code ZIPs
  into the existing resumable downloader even below the component size threshold.
  Small component downloads retain their prior behavior. Cache: `cache/updates`.
- The exact GitHub tagged repository asset path is allowed by the existing
  downloader; arbitrary GitHub URLs and branch URLs are not allowed.
- ZIP extraction stays in an owned `versions/.stage-*` directory. Traversal,
  symlink entries, duplicate/case-colliding files and oversized inventories are
  refused. Maximums: 10,000 entries, 256 MiB expanded code, 2 GB downloaded asset.
- Before publication, `update_health.py` executes under the existing private
  Python, compiles the candidate Python sources, imports GUI modules, and runs
  read-only candidate `Config` preflight without GPU inference. Existing config
  is passed in memory with `code_root=<stage>`; no projected config copy is written.
- The verified healthy version is renamed into `versions/<version>`. An existing
  differing version is preserved and rejected. Old working versions are retained.
- Packaged `Config` resolves effective code from `current.json`; legacy schema-1
  layouts without `application_home/current.json` retain their previous behavior.
  Stored `install_root` remains a legacy hint. No user config field, byte or mtime
  is changed by an update. There is no second active-version pointer.
- `run/update.lock` serializes updates and new launches. Launcher-held
  `run/sessions/*.lock` files block switch while GUI/workers are alive. Direct
  lecture/dialogue worker locks are also held during apply and crash recovery.
- `run/update-transaction.json` journals exact previous pointer bytes, the next
  pointer and a random first-launch token. `current.json` is flushed and replaced
  atomically only after stage health succeeds.
- A real private-pythonw first launch must initialize the main GUI successfully,
  write a token/version/PID receipt and remain alive through a two-second grace
  period. The readiness deadline is 45 seconds. Failed initialization, exit or
  timeout terminates only that trial process and restores the exact previous
  `current.json`. The trial token is removed from the GUI environment before
  future worker commands can inherit it.
- A pending journal is recovered before a normal stable-launcher session, or
  explicitly with `recover`. Recovery waits for no sessions/direct workers:
  after an updater crash, close any surviving trial GUI first. No process is
  guessed or killed during crash recovery. Config and user data are not restored
  from backups because the updater never writes them.

## Acceptance evidence

Real read-only discovery is recorded in
[phase2a-github-2026-10-05.json](phase2a-github-2026-10-05.json): the endpoint returned
published prerelease `v1.9.5-beta.1`, release ID `399655135`, so the same installed
version correctly reported `no-update`. No new real release exists for a live
server-side switch test.

The final disposable gate is `%TEMP%/LP2a-20261005-d`, installation
`Программа 课程`, newly initialized data `Данные 课程`.
[phase2a-native-2026-10-05.json](phase2a-native-2026-10-05.json) records:

| Acceptance | Evidence |
| --- | --- |
| Newer version | Tagged fixture `1.9.6-fixture.1` discovered/installed over `1.9.5-beta.1`; ordering/channel cases in targeted tests |
| Interrupted ZIP | Deliberate fixture timeout at 65,536 bytes; the real downloader sent Range, validated 206 and resumed the ZIP |
| Successful stage/switch | Actual health subprocess, verified side-by-side publication and atomic pointer switch; real main window `Lecture Pipeline · 1.9.6-fixture.1`; 6.297 s for the fixture update |
| Bad/missing manifest, ZIP/hash | Targeted tests reject missing/bad/incompatible manifest, bad SHA and invalid ZIP with a matching outer SHA |
| Broken stage | Deliberate syntax error rejected by the real health subprocess; current pointer unchanged |
| Failed first GUI launch | Deliberate GUI adapter initialization error; trial process rejected and exact previous pointer restored |
| Simulated updater crash | Pending journal plus switched pointer; real recovery restored the exact old bytes |
| Active GUI/workers | Actual live GUI blocks the native gate; real OS session/direct-worker lock tests block both apply and recovery |
| Data/config | SHA-256 and mtime unchanged for config, a real fixture Word document, vocabulary XLSX and lecture/AI state |
| Verified reuse | Repeated no-update/apply and manifest/archive fetches require no network; verified cache events recorded |
| Recovery usability | Retained working GUI launched again after rollback/recovery and closed cleanly; old original version still present |

Fixture release metadata and HTTP streams are explicitly supplied in memory;
they are not published GitHub assets. Health, extraction, hashing, filesystem
locks, atomic pointer operations and GUI processes are **not mocked** in the
native gate. Private immutable runtime/model files are hardlinked read-only from
the prior disposable qualified candidate. User data/config are created fresh,
not copied from another installation. Production and baseline roots are untouched.

Targeted tests passed: **15 updater/config-contract + 21 download/resume +
8 bootstrap + 21 ASR/config = 65 tests**. Relevant commands:

```text
python -B -m unittest discover -s tests -p "test_update*.py" -v
python -B -m unittest discover -s tests -p "test_*downloads.py" -v
python -B -m unittest discover -s tests -p test_bootstrap_flow.py -v
python -B -m unittest discover -s tests -p test_asr_devices.py -v
python -B tests/native_updater_gate.py --prepare <new-LP2a-name> <qualified-disposable-base>
```

Reviewable commits: `51c2c11` pointer/launch contracts; `b9bcce3` updater and
release builder; `fe2ff0c` GUI legacy-import regression; `59a7254` direct-worker
recovery guard; `da63ed8` real first-launch initialization defect; `3952bcf`
small code-ZIP resume and native gate. Failed gates `-a`/`-b` remain diagnostic
fixtures; `-c` passed the core flow and `-d` passed the final resumable flow.

## Limits of this slice

Only code updates on a Phase-2a-capable stable launcher/base are supported.
Already distributed Phase 1c packages do not acquire this new updater magically;
shipping the capable base requires a separate release decision. This updater
does not modify/repair the bootstrapper, stable launcher or private runtime.
The old Setup.exe is not an updater/repair route for an updated installation.

Health checks are bounded startup/preflight checks, not a full lecture regression
or rollback after an arbitrarily late application failure. New component/runtime
requirements and data migrations are rejected. Cache/old-version cleanup, UI
polish, background checks and stronger release authenticity remain out of scope.
No remote end-to-end update of an actually published newer release is claimed.
