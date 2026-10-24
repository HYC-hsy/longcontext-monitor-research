# Earlier 12-task GA-only arm: visible-content backfill

This directory contains the 12 condition-A / GA-only real episodes from the `pma12_native_r1_20261015` A/B batch. Their run IDs happen to begin `pma-`; method identity comes from condition A and the frozen manifest (`GA_only`), not the ID prefix. The executing source identity recorded for this batch is `5f585523ea8b817c8a0761a98f82f38428f4ef1c`.

Each run directory has `task_turns.jsonl` (actual Task-visible request, public response blocks, tool calls, and later visible receipts), `events.jsonl` (the full recorded event sequence), `evaluation.jsonl` (public terminal/CTRF summary), and `INDEX.json` (private source byte hashes, public file/line hashes, source-line mapping, and redactions). These are redacted, re-encoded projections rather than raw HTTP bytes. Hidden reasoning, credential-like values, private configuration/metadata, and URLs are removed or replaced. Original run files are unchanged and retained locally.

The corresponding B-arm PMA episodes are **not** represented by these A-arm packages. No model, Task, or verifier was called for this backfill. The per-run inventory records what remains unavailable publicly for the B arm and other historical variants.
