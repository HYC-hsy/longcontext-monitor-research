# CRS-v0.1 minimal correction (zero-model)

Parent candidate: `9191b47c260ccbff7a8320cfcd23f7a541283981`.

Production diff is limited to `monitor_agent_core/crs_v0.py` and one root-frame condition in `monitor_agent_core/agent.py`. `ase_v0.py` (including `SYSTEM_PROMPT`), runtime, provider, Task Book, Echo, Situation, feedback barrier, seven tool names, and non-CRS paths are unchanged.

## Provider-visible cited provenance

The active CRS surface now contains the exact model-authored canonical contrast plus a mechanically rendered, bounded record for its own cited ground and observation locators. Source hashes/cursors, file-read requested and returned ranges/SHA/truncation, code-run session/status/exit/error/cancel/running data, receipt hashes, and public Task tool-result counts/hashes are taken from the resolved sources. Public tool-results receive a raw JSON serialization excerpt capped at 640 characters with source-character count and truncation flag. Long metadata strings are mechanically clipped for transport; the full resolved provenance remains in audit/state identity. The whole CRS surface is capped at 16,000 characters, checked before accepting a new proposal. No automatic recent-observation selection or semantic adequacy judgment is added.

Illustrative shape of the cited-provenance portion, with hashes omitted here only for readability:

```json
{"ground_refs":[{"locator":"monitor/reference.md","source_sha256":"…"}],"observation_refs":[{"locator":"monitor/audit/dialogue.jsonl#2","source":"supervisor_tool_result","tool_name":"code_run","receipt_sha256":"…","lifecycle":{"status":"cancelled","session_id":"s1","exit_code":null,"cancelled":true}}]}
```

The actual provider surface includes the hashes and explicitly states: `mechanical provenance only; no adequacy/support/verdict is supplied by runtime`.

## Release-state identity

`canonical_contrast = JSON(contrast, sorted keys, compact separators)`.

`canonical_resolved_provenance = JSON(resolved ground_refs/observation_refs, sorted keys, compact separators)`.

`state_digest = SHA256(UTF8(canonical_contrast + "\n" + canonical_resolved_provenance))`.

The existing contrast digest and the new provenance digest are logged separately. Confirmation requires the same current handoff identity, canonical contrast and state digest, a provider-ready exposure of that exact stored state, and a later model turn. A changed current Task Book SHA produces a new state even if the model reuses identical text, and must be exposed for another turn. Historical Supervisor tool receipts are re-resolved from their audit rows; later live workspace changes do not change that historical receipt's identity. No post-boundary measurement is required.

## Scope and tests

CRS tool schema is selected only for an ASE root frame. Local ASE provider-ready schema matches the parent candidate's ordinary seven-tool schema; in root only `allow_complete` differs. The local intervention/follow/patrol path is unchanged.

Zero-model command from `GenericAgent-main`:

`python -B -m pytest -q tests/test_crs_v0.py tests/test_curator_supervisor_v0.py tests/test_ase_v0.py tests/test_dcm_v0.py tests/test_clean_monitor_runtime.py tests/test_monitor_provider.py`

Result: 143 passed, 8 skipped. No Task Agent, Supervisor provider, native evaluator, or scientific trial was called. The local pytest installation emits an atexit permission warning about an older temporary directory after exit code 0.
