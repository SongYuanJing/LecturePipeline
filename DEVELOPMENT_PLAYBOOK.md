# Development playbook

1. Production is never a development tree. Inspect actual release/state before dangerous work.
2. User data is separate from code. No automatic reprocessing, silent state resets or implicit migration.
3. Bugfix scope stays minimal. Target tests to the blast radius; full relevant regression for release or a shared/fundamental layer change.
4. GUI cosmetics do not require Whisper regression. ASR changes require ASR tests/smoke. Atomic/state changes require broad transaction tests.
5. Destructive scenarios use disposable workspaces only. Do not run tests whose result cannot change a decision.
6. Release only a verified candidate, preserve evidence/checksums. Migrations require backups, validation and reversible compatibility. Updates stage side-by-side and rollback; no in-place user-data replacement.
7. Treat Work/Codex budget as finite. Do not expand a bugfix pass into architecture work. Use the working beta; add functions only from demonstrated needs.
8. Source assets only in Git. Never add private config, user paths, audio, Word/XLSX, model, runtime binaries, credentials, logs, state/history or experiments. Inspect staged content before any remote push. No remote is configured by default.
9. Build from locked verified components. Run `scripts/run_tests.py --config <disposable-config>` with candidate Python after staging a package. Packaging tests must not register tasks or load long audio. One short smoke is enough for packaging runtime integration.
10. Next beta gate is clean-install validation on a disposable Windows profile/VM. Keep stable production intact. Publish only separately authorized tagged releases, never main as an update source.
