# Public development replay: literal wrapper versus explicit decoded-field citation

## Result and boundary

The replay contains 32 evidence references from actual public model/tool logs across 13 distinct raw sources. These are all references whose original quoted text was absent or non-unique in the selected raw source, not 32 independent tasks or failed cycles.

- Pinned baseline binder at `016984a9f6f24d0fb1d330fd17feb8b3dd14c926`: 29 `quote_not_visible`, 3 `ambiguous_quote`.
- New production `_project_tool_text` + registration/rendering/binding, with an explicit developer-authored field-path selection: 26 exact matches; 3 `quote_not_visible`; 3 `ambiguous_quote`.
- With the citation still pointing to the raw parent rather than the selected decoded child, all 32 references remain `quote_not_visible` because the JSON string bodies are not displayed in the parent's visible spans.
- Four deterministic unittest tests pass. Zero model calls, real reruns, hidden-evaluator reads, or original-run changes.

The replay retains each historical quote exactly, including LF, CRLF, quotation marks, and HTML/Python code. It changes the cited handle to the production-generated child for the selected public field. This is a controlled representation/interface check, NOT a claim that unchanged historical responses pass the new API, that a model will select the child, or that online decisions/completion improve. It does not replay whole memory-operation transactions or resolve IDs; those require their own tests. Counts in archived runs and their evaluation remain unchanged.

## Actual examples and remaining failures

- SQLite C2: original listing quote with a real newline binds exactly to `observation/tool_results/1/content/stdout`.
- SQLite C7: real package output with CRLF binds to the decoded stdout without newline normalization.
- SQLite C9 command quote: embedded `CFLAGS="--coverage -O0 -g"` binds to `commands/1/args/script`.
- SQLite C10/C11/C12/C16/C17: actual multiline output quotes bind to their selected stdout fields.
- HTML C2: actual `JSRemovalParser` code, including docstring quotes and newlines, binds to `commands/0/args/content`.
- SQLite C4 and C9: quotations omit intervening source lines. The test verifies their component lines occur in order but the whole quote is not contiguous. They remain rejected.
- SQLite C15 op1: the selected output does not contain `Setting up make (4.3-4.1build2) ...`. A different source in the same actual prompt does contain it; the fixture retains that witness. The wrong-source citation remains rejected; the replay does not silently search another source.
- SQLite C14/C15: three compiler-command quotes have multiple occurrences in their decoded sources. They remain ambiguous, without accepting a first match.

The 26 recovered references include repeated citations to the same historical source across cycles. Do not interpret this as 26 independent improvements or recompute original cycle acceptance from these reference-level results.

## Data provenance

`real_public_fixture.json` is a bounded, deduplicated development fixture extracted from the two public archives under `experiment_runner/evidence_gap_two_real_visible_20261025/` at baseline commit `016984a9...`: SQLite `pma-e8b1699a9e2b4a43`, HTML `pma-ee5cd9d22ff34012`. Audit copies under `/workspace/shared/sqlite_audit/` and `/tmp/html-audit/` were verified byte-identical to the archived public gzip contents. No hidden transport, reasoning, evaluator, or native-result file is used.

Each case identifies its exact prompt archive, JSONL line, original source line SHA, transport archive/line/SHA, operation index, evidence index, historical source handle, raw text SHA, unchanged quote, and explicit mapped child path. Whole gzip hashes are recorded. Tests regenerate the fixture from public archives and require exact equality. `run_real_replay.py` imports the real baseline binder from the pinned Git commit and records its SHA, then compares it against the current production projection and binder. `real_replay_report.json` records all 32 results and implementation hashes.

Original event envelopes are not reconstructed from prompt snippets. Replay registration therefore labels its digest `public_prompt_extract`; it does not pretend to recover an accepted-event digest or reuse original source IDs. Parent/child source linkage and parent raw text are verified using production registration.

## Reproduce

From this candidate directory:

```sh
python evidence_interface_repair_v1_offline/extract_real_replay.py
PYTHONPATH=. python -m unittest discover -s tests -p test_gap_evidence_real_replay.py -v
python evidence_interface_repair_v1_offline/run_real_replay.py
```

The extraction, replay runner, and test contain fewer than 400 combined code lines. No production file was edited for this replay. `pytest` is absent from the current default Python, so the successful test execution uses standard-library unittest rather than installing dependencies.
