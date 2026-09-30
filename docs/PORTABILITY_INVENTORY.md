# Packaging-relevant inventory

| Boundary | Class | Resolution |
|---|---|---|
| Data root / sync drive / subjects / workspace / languages | A configurable, C first-run, E local config | External absolute user-selected data root; subject/workspace data in config; no university/semester/letter assumption |
| Code root, launcher, logs, worker homes, AI queue, dictionary backups | B relative | application_home separates mutable files from versions; code root resolves from config |
| System Python / Codex document Python / venv launch paths | B, D component | Private pinned 3.11 ASR and 3.12 document components; relative paths; isolated _pth |
| User HuggingFace cache | D component | Owned HF-layout cache with offline verified import; legacy config default retained only for backward compatibility |
| CUDA DLLs / model binaries | D optional/separate | Explicit hash-verified component imports, no binary Git and no driver install |
| Task Scheduler names / execute / user / shortcuts | B,C,E | Fresh UUID prefix, current Windows user, private pythonw + stable launcher; app-root shortcut |
| GPU hardware/driver, filesystem availability | E | Preflight capability probe and existing CPU fallback; no fixed GPU model |
| Historical test-lecture filtering | A | hidden_tasks config; empty on first-run; legacy default retained for old schema-1 config |
| Real Word/Excel/Drive IDs, manual ChatGPT | A/E external user data boundary | No migration/adoption or chat-state dependency introduced; manual AI remains external |
| Historical one-off rollback scripts | excluded | Not portable runtime code; baseline export inventory documents included source only |

No current user name, drive letter or real course names are embedded in portable config. Absolute data paths deliberately remain in generated per-installation configuration; they are not source assets. Runtime fallback defaults for legacy non-packaged installs remain for compatibility.
