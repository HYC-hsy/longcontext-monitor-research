# GA-only SQLite unified-entry check (2026-10-22)

## Scope and source

- Source commit at both the final fake acceptance and real launch: `f4f0eaafd412f91392b3f806f452b410245b924d`.
- One `sqlite-with-gcov` slot, occurrence 1, serial execution; condition `A`, research candidate `U` (GA-only). No `runtime_policy` was supplied.
- Local private configuration and raw task logs are not in this repository. The public reusable example is `examples/sqlite.ga-only.json`.
- The shared Harbor adapter is loaded from this repository's `long_context_bench/adapters/harbor_ga_agent.py`. Git and working-tree bytes are LF, SHA-256 `82ac43f2c791bc4d8510e1d851ef7b2c5bead8cdfbb847be36c7ae244821ecce`; its primary pin matches. The prior CRLF byte variant is not accepted as the primary identity.

## Offline checks

- `E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe -B -m unittest discover -s experiment_runner -t . -p test_*.py`: 63 tests, OK.
- Final-source A-only Harbor fake fixture: run `pma-3b60dd417cd240b8`, controller exit 0, synthetic file/HTTP sentinel reward 1, cleanup clean. This is synthetic, not a SQLite score.
- The A-only evidence directory `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/ga_only_cert_20261022` passed `verify_evidence(..., conditions=('A',), require_committed=True)` with 19 required-file hashes. The historical A/B requirement remains the default.
- Unified `experiment_runner prepare` and `run`, using a separate one-slot fake config: run `pma-73db02dced32428d`, `zero_model_fixture_only=true`, controller exit 0, Task fake captures 2, synthetic native sentinel reward 1, no auxiliary worker, cleanup confirmed. Its one-time fake authorization was removed. This proves the unified entry reached the existing Harbor backend, not live model capability.

## Real attempt and exact limit of its result

Commands used with a separate local, ignored, real configuration:

```text
python -m experiment_runner catalog --config experiment.ga.real.local.json --output E:\ga-real-catalog-f4f0.json
python -m experiment_runner plan --config experiment.ga.real.local.json --output E:\ga-real-plan-f4f0.json
python -m experiment_runner prepare --config experiment.ga.real.local.json --output E:\ga-real-sqlite-f4f0
python -m experiment_runner run --config experiment.ga.real.local.json --output E:\ga-real-sqlite-f4f0
```

The actual interpreter was `E:\LongContext\bench_runtime\pma_native_venv\Scripts\python.exe`; the `run` process exited 0 as a controller process. Run ID `pma-a927e53b0aef4e8e`. Manifest SHA-256 `5ab7cde4f8267a8659db92909be26b4bfc6d3bc0962d6f6affdf0dface4ec3f8`; frozen config SHA-256 `fc04ff4fed66a999bfea5fc56bb913b63e04932afd87d0fcc59bfaacb87499e3`. The one-time authorization's original SHA-256 was `d4d2fca47bba97f5d60cbb3b30e04f383c9818c1d33c26845e51e988e3976081`; the authorization file was removed after the run. The native task used the existing GA configuration: 300-turn maximum and 14,400-second Agent wall limit, not the original 900-second Agent protocol and not uncapped. Its verifier retained the task's 900-second limit.

The GA emitted one `provider_request_attempt`. The response was HTTP 403, classified `http_error`; the safe supplier error code was `SUBSCRIPTION_NOT_FOUND`. There was no valid Task model response and no tool call. Terminal record: `PROVIDER_FAILURE`. No PoS, PMA, or stateful auxiliary call/worker was enabled. The supplier denial is an external access condition; it does not establish that the adapter or Task logic is correct beyond this point. No alternative model, profile, credential, or blind retry was used.

The existing Harbor lifecycle then ran one native deterministic verifier, recording reward `0.0` and controller `harbor_return_code=0`. This is an evaluated infrastructure-failure artifact, not a completed GA attempt or evidence of task-solving failure. The verifier ran once; no second evaluation or episode was started. Cleanup reported no remaining containers, no cleanup errors, a clean owned volume, and no identified live process. The private raw records were retained; no private endpoint, credential, or error body is published here.

Raw private-byte hashes (not hashes of this public summary):

| Artifact | SHA-256 |
|---|---|
| `archive/live_result.json` | `d648290d99150771daf6c3d77e3a665a8e6920a1bb01aedf95b46c410758bdf8` |
| `agent/research_events.jsonl` | `3570b759deedbef5e38d37b2c3c0808591aed12be5ed97e0137f00fdbbae3c7d` |
| HTTP error body (private) | `df92124cb368e583b544065e58ddc0438ee3563b397f8412abbc4160d11f6ad9` |

## Acceptance boundary

Verified: configuration selection, preparation, bound launch, GA-only identity, real provider HTTP attempt, native evaluation invocation and cleanup. Not verified: an effective Task response, real tool execution, or a full GA task-solving loop. This task stops at the supplier's access denial; resolving the subscription/group entitlement requires an authorized account decision, not a code or protocol fallback.
