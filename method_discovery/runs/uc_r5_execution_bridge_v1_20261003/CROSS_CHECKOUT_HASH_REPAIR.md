# Bridge source identity portability and raw receipt preservation

This follow-up is limited to the research bridge, not the candidate or preregistration. On Windows with `core.autocrlf=true`, an identical Git source blob may appear with LF or CRLF bytes in different worktrees. The first addendum's raw-worktree source hash could therefore reject a legitimate checkout. `bridge_source_hash()` now canonicalizes Python source line endings before computing its SHA-256. The offline regression simulates a CRLF checkout and requires the same identity.

The earlier zero-model receipts were copied byte-for-byte from the generated pytest directories. Git's text normalization can alter the bytes of individual JSON exports on a fresh checkout, so `RAW_RECEIPTS.zip` preserves the four generated JSON receipts as binary archive members. Its SHA-256 is `273ef29aad6b3e6915f93c3d439517f8bf24efe8c9b206555dce19fe873232b9` and size is 1,823 bytes. The nonbenchmark `/app` tar is itself binary and remains separately committed.

No deployed profile, candidate mechanism, frozen runner, task, image, tool schema, gateway transport file, or scientific slot was changed. The subsequent execution addendum must reference the new research implementation commit and canonical source hash; the old addendum remains in Git history.
