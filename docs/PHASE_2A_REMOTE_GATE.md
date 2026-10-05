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
