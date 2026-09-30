# 1.9.5-beta.1

- GUI first run, verified component imports, workspace/subject setup and isolated Windows integration.
- Add ordered lecture parts through the GUI using the existing READY/worker path.
- Export a self-contained ChatGPT task and import a validated result through the existing local finalizer.
- Windows DPI/readability and Add Lecture modal sizing fixes; explicit CUDA source selection.
- User-confirmed three-part GPU ASR → manual ChatGPT → Word/vocabulary (+13) → completed acceptance.
- No ASR parameter, dictionary merge, Word schema or H3 publisher changes in this release tail.

# 1.9.4-local-finalize-candidate

- Explicit local AI finalizer uses the existing Word builder, dictionary merge, queue APIs and unchanged H3 publisher.
- Local file URI/source hashes replace mandatory Drive IDs for local provenance; legacy Drive receipt support remains.
- Empty vocabulary, resume/idempotency and private Python direct-entry support.
- 109 targeted checks passed before release tail; one real external-result smoke and an idempotent rerun passed. No ASR rerun or production changes.

# 1.9.3-thin-candidate

- CTranslate2 4.8.2 moved to pinned external offline import with cp311/AMD64 native validation.
- Independent component states, CPU/GPU capability and base integrity before setup.
- Public ZIP enforces complete CTranslate2 ownership exclusions.
- ASR/application business code and PyAV importer unchanged.

# 1.9.2-thin-candidate (local validation)

- Pinned offline PyAV component import with RECORD/path/ABI/hash validation and staged publish.
- Remove PyAV native stack and CTranslate2 cuDNN copy from built artifacts; fail build on reintroduction.
- Component status and prerequisite validation before workspace initialization.
- ASR/business code unchanged. Public release clearance remains pending.

# Changelog

## 1.9.1-candidate РІР‚вЂќ deployment validation

Integration explicitly uses UTF-8 so Unicode data paths work without inherited Python encoding settings. Bootstrap now validates private ASR/document native imports before initializing user data; missing runtime errors name the prerequisite without a traceback. Portable artifact names retain the full version. Package now includes collected license texts and a binary inventory, with public distribution explicitly uncleared. No ASR/state/dictionary/Word changes. Real disposable integration, short worker smokes, uninstall and reinstall are recorded separately; reboot/login remains an external gate.

## 1.9.0-candidate Р Р†Р вЂљРІР‚Сњ packaging foundation

Separate local source repository; additive application-home/task-prefix config; versioned code and external user data; private Python/Word runtimes; explicit offline model and optional CUDA imports with hashes; portable ZIP bootstrap, integration plan and data-preserving uninstall. No data schema, ASR profile, H3 transaction or GUI design change. Not installed over production.

## 1.8.1 Р Р†Р вЂљРІР‚Сњ baseline

Selected installed stable source exported with original SHA256 inventory; Git text normalization applies to source history. Frozen baseline includes H1/H2/H3/M1 fixes. No production data/config, historical personal migration scripts or binaries in Git.
