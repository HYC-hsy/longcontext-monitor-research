# Independent probe cursor repair (2026-09-19)

The common C/D probe base is frozen at public commit `8addbf5` (root
development commit `af270c3`). `file_read` now exposes the already-supported
`offset` and `max_chars` arguments. The returned `next_read` cursor can be
passed back without restarting a long first line.

The regression constructs a multi-line long record, repeatedly feeds the
returned cursor into the next offline read, and asserts exact reconstruction,
no duplicate cursor, and no missing content. The provider/model, request
budget, history, compression, and D expectation protocol are unchanged.

Both C and D must use this same frozen base in subsequent experiments.
