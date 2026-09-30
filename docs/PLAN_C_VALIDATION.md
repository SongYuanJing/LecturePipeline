# Plan C technical validation — 2026-09-28

Version: 1.9.3-thin-candidate. Technical gate passed; independent Windows/public Beta validation remains open.

A new disposable installation was extracted solely from the new public ZIP. Pinned supplier wheels, model and optional CUDA were imported through the package entry points. No application file was borrowed from production, source or a host runtime. Tests run on the existing Windows host, not a fresh VM; the child Python environment and import paths were isolated. A standard USERPROFILE pointing to an empty disposable directory was necessary for application preflight; no user HuggingFace cache was used.

- 29 targeted regression tests passed, zero failures/errors/skips: CTranslate2 import/exclusions, existing thin-package and first-run tests, eight relevant packaging checks.
- Actual supplier CT2 wheel: complete 33-file archive validated, cp311/AMD64 native extension loaded before atomic directory publish. Repeated import reused it. Forced termination before publish left staging only; retry cleaned it and succeeded. A deliberately corrupted disposable component was rejected and preserved. Primary good component stayed valid.
- Actual component combinations: PyAV missing/CT2 valid, PyAV valid/CT2 missing, both valid/model missing all blocked correctly; model imported/no CUDA enabled CPU; verified CUDA enabled GPU. Invalid states also covered by regression fixtures.
- Real CPU smoke without a CUDA component: large-v3, int8, VAD=false, beam=5; 10.2456 seconds of disposable audio, 8.093 seconds model load, 39.390 seconds total. Private imports/model only. Supplier CT2's own cuDNN was retained and loaded, as allowed by the Plan C contract.
- Real Dialogue smoke after verified CUDA import: cuda/int8_float16/VAD=true, existing beam/VAD parameters; 11.281 seconds load, 2.531 seconds transcription, 15.000 seconds ASR child, 16.484 seconds complete job. TXT/SRT/DOCX produced and hashed; completed job was idempotent. The synthetic English fixture used a Russian system voice and auto detected ru; this test checks packaging execution, not recognition quality.
- Setup and production-equivalent preflight passed against disposable config/data. No tasks were registered or production workers changed.
- Public ZIP CRC, all per-file hashes, exclusion rules and remaining inventory hashes verified. PyAV importer and all src/app files are unchanged by Plan C. Decode matrix, Lecture smoke, H3 and full deployment audit were deliberately not repeated.

Detailed machine-local logs, timings, file paths and release hashes are kept outside the public repository. Final ZIP identity is recorded in its adjacent SHA256 JSON and local release record. Production writes: zero.

Next stage only by separate request: independent clean Windows, logon/reboot, task autostart, supplier provisioning, short smoke, uninstall/reinstall, then GitHub repository/Beta. No redistribution-clearance assertion for externally supplied wheels.
