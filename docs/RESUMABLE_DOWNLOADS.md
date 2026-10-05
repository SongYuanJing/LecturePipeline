# Large pinned artifact downloads

The Phase 1c native gate exposed repeated loss of a partially downloaded 3.09 GB
model after a supplier read timeout. Large files now use bounded resume in the
existing Python downloader. The .NET shell does not resolve components.

`fetch(..., expected_size=...)` enables resume for pinned files >=128 MiB.
CUDA wheels already pin exact sizes. The model manifest adds the additive
`file_sizes.model.bin=3087284237` field; revision and all SHA-256 pins are unchanged.
Small downloads retain their existing unique temporary-file behavior.
Phase 2a code-only update ZIPs explicitly opt in with `resume=True` plus a pinned
size, including below 128 MiB. Component callers retain the threshold/default.

Inside the artifact's SHA directory, `.partial` and `.partial.json` store an
unfinished file, source URL/name/size/SHA identity, durable offset, prefix SHA-256
and optional strong ETag. An advisory lock serializes writers. The prefix hash
detects local corruption; **it does not authenticate supplier content**. On retry,
identity, bounds and the saved prefix hash are checked before issuing Range.
Uncheckpointed crash tails are truncated. Corrupt/oversized/mismatched prefixes
are discarded. Checkpoints occur every 8 MiB and on graceful timeout/cancellation.

Range requests use `Accept-Encoding: identity`, an exact byte offset, and
`If-Range` when a strong ETag is available. A 206 response must have a compatible
Content-Range start/end/total, body length and ETag. A whole 200 body replaces the
prefix; an incompatible range/identity or 416 resets it before another request.
See [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html#name-range).

Each invocation permits at most three requests, with 1/2-second interruptible
backoff for transient failures. Reads remain bounded by 60 seconds. Exhaustion
reports failure and preserves the safe prefix for explicit Retry. Cancel leaves
an unfinished prefix, never a ready artifact. A hard process termination can lose
the tail after the last checkpoint, not the entire validated prefix.

Publication requires exact size, streamed SHA-256 and a final on-disk SHA-256
pass; only then is `.partial` atomically renamed to the normal cache filename.
Final hash mismatch discards the prefix and fails, without importing anything.
No per-chunk supplier hash or alternative model source is introduced.

Targeted tests in `tests/test_resumable_downloads.py` cover resume, ignored Range,
incompatible range/identity, partial corruption/oversize, timeout and cancellation,
retry exhaustion, crash tails and final size/hash rejection.
