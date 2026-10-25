# Offline graded-alignment replay

No model requests, real Tasks, or evaluator calls. Original archives are read-only.

## Findings

- Original archived submissions: 49 quotes, 44 literal associations (42 unique, 2 multiple), 5 unbound. These are observed historical counts, not a new full-catalog replay result.
- Restricted retained-source replay: all 49 submitted quotes evaluated against only recoverable, hash-valid, cycle-visible snapshots. Result: 38 exact associations (36 unique, 2 multiple), 11 unbound. This is **not** a regression estimate or comparable full-catalog 38/49 result. Six historical matches lack their valid original source bytes in this public projection.
- C8: both actual decoded quotes match event-15 decoded stdout after controlled formatting normalization. The stdout equals the existing C8 fixture and its retained SHA-256, a3a8f7483bb3d4a2d2ad9a3cec6885d4634dfc6bb4ec351d560d2c2a70d2a3f6. Original manifest confirms the entire [0,7533) stdout was visible. Both grades are normalized_unique **within this one source projection**, not certified unique across discarded sources.
- C5: all three actual `[hidden gap]` quote submissions remain unbound with omission-marker refusal.
- C6: the actual first quote and retained source texts, in a fresh store with an explicitly unbound derived parent, give exact_multiple / mixed provenance / bound. The clean raw alternative is preserved; serialize/reload equality passes. This is a targeted provenance test, not full historical bank migration or full C6 operation replay.
- Synthetic negation example produces fuzzy_candidate despite changing meaning. This explicitly demonstrates why fuzzy association is not proof. The finite-work example returns unbound / approximate_work_limit_not_searched, not Task failure.

## Public projection limitation

Four SQLite public-projection blobs differ from their retained original hashes. All four contain `[REDACTED]`: stdout and parent wrapper for events 5d8a4989164a4603bbf8790b689fe984 and 8d5a5cf39daa446387207d3e93f6520a. Exact source IDs and original hashes are in replay_results.json. This is consistent with documented public redaction, not evidence of private/archive corruption. Original hashes were not recomputed or patched. Missing unmatched sources are also not retained in the bank. These limits prevent full-catalog replay and uniqueness certification; they do not block code acceptance.

## Reproduction

Use the selected project interpreter with its existing dependencies and module paths. Supply all four existing public-projection files explicitly; the script has no machine-specific input or output defaults:

    python replay_archives.py \
      --sqlite-memory <sqlite-public-memory.json> \
      --sqlite-events <sqlite-public-task-events.jsonl> \
      --html-memory <html-public-memory.json> \
      --html-events <html-public-task-events.jsonl> \
      --output <replay-results.json>

The script locates the committed C8 fixture relative to its own directory. `PYTHONPATH` must include the implementation directory, its tests directory, and the project's existing vendor dependency paths. No extra downloads are required when using the supplied public projections and existing project environment.

Source archive: HYC-hsy/longcontext-monitor-research, exact commit a3ba4c0d869c0149ba10ca6a698deecbb16dd0e9. Relative to the implementation directory, the supplied compressed public projections are:
- evidence_alignment_v2_two_real_20261025/01-sqlite-with-gcov-r1/memory.json.gz
- evidence_alignment_v2_two_real_20261025/01-sqlite-with-gcov-r1/events.jsonl.gz
- evidence_alignment_v2_two_real_20261025/02-filter-js-from-html-r1/memory.json.gz
- evidence_alignment_v2_two_real_20261025/02-filter-js-from-html-r1/events.jsonl.gz

Pass their already-decoded JSON/JSONL files to the CLI. The verified SHA-256 values below refer to the decoded bytes, not gzip containers. The root retrieved these exact existing archive objects; this script performs no downloads.

Verified input byte SHA-256 values:
- SQLite memory: faaca7a4a4b1a2488732a2f50860a473a8ccb12947d802ece5996d4dc83fe512
- SQLite events: 20fe258351ee5a814f1d8179a2205bdd2f7f2548eb4bd381bb376500192f1fb5
- HTML memory: 9e18654f484381cfaad89e453d8f5fae52ecce156e8fcd82c0cc7d01f091a167
- HTML events: 436eea7a8ce480b4783011ef0c3aefd9a3307e8c2f04d690940c87daf50983ac

CLI replay preserves all case outcomes and original-source checks. Timings and fresh-bank randomly assigned revision/source IDs vary between executions; these IDs are not historical archive IDs.

Timing uses perf_counter, fixed one-source catalogs, 10 measured repetitions, no warmup. Exact parameters and min/median/max are in the report. FUZZY_WORK_LIMIT is 2,000,000 estimated DP cells per evidence operation. These local timings are engineering diagnostics, not online latency or effectiveness evidence.
