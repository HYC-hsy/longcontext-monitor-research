# PMA-gap-evidence: two real-task diagnostic attempts

Both authorized episodes reached native evaluation, but **neither exercised a successful auxiliary-model response or evidence-bound write**. Every maintenance and selection call failed with the auxiliary service's public `billing_error: insufficient balance` message, surfaced by LiteLLM as `APIConnectionError`. The Task model used its separately configured route and continued. Therefore the scores below are Task outcomes under an empty/stalled memory view, **not evidence that the new memory method works or improves outcomes**. No episode was retried and no extra evaluation was requested.

## Frozen identity and results

- Execution source: `27d2d22e675b56873d8dc5a3693738ed15e87f06`; the certified runtime-code commit was `f552fd7e766c9addabf92d614772cbff2d091240`. Committed A/B certificate `cert_evidence_gap_v1_final_20261025` passed `verify_evidence(require_committed=True, research_candidate='pma_gap_evidence_v1')` immediately before preparation. No execution code changed during either episode.
- Dataset commit: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`. Catalog confirmed the exact second ID `filter-js-from-html`, distinct from `break-filter-js-from-html`. Both slots were B / `pma_gap_evidence_v1`, serial, one occurrence each.
- Both profiles identified model `claude-opus-4-8`, with separate Task and PMA transport configurations. Profile file SHA-256s: Task `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`; PMA `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`. Credentials and endpoints are not included.
- Agent time and Task turns were uncapped research diagnostics; official verifier limits remained 900 s (SQLite) and 1800 s (HTML). `download_retry_v1` was frozen with `max_attempts=3`; both evaluations reported `evaluation_completed` and exactly one test-entry start. These are not original Agent-time-condition benchmark scores.

| Task | Run ID | Task requests / responses | Task tool calls | Memory cycles | Auxiliary logical calls | Accepted writes / validation rejects | Reminders delivered | Native report / reward |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: | --- |
| `sqlite-with-gcov` | `pma-4549208caddd4405` | 16 / 16 | 15 `code_run` | 16 | 16 maintenance + 16 selection, all `APIConnectionError` | 0 / 0 | 0 | CTRF 3 passed, 0 failed; 1.0 |
| `filter-js-from-html` | `pma-3f91154dd17a4f6f` | 2 / 2 | 1 `file_write` | 2 | 2 maintenance + 2 selection, all `APIConnectionError` | 0 / 0 | 0 | CTRF 0 passed, 2 failed; 0.0 |

There were no model-produced write batches to classify as an accepted batch, reference-validation rejection, or successful no-op. Each cycle attempted both original phases and recorded transport errors; neither Phase 2 produced a valid silent decision or reminder. The longest continuous memory stall was 16 cycles for SQLite and 2 for HTML. Unknown source, quote mismatch, ambiguous quote, and argument-parser errors were **not observed**, because the maintenance model never returned tool calls. Final knowledge, procedural, status, and gap views were empty for both episodes; their evidence stores contained zero sources, revisions, or receipts. This does not test whether legal quotes would bind or whether legal-but-wrong interpretations would be caught.

The public Task trajectory shows SQLite used 15 shell actions involving source/build, compiler, gcov and PATH work before normal completion; its native tests passed. In the HTML task, Task wrote `/app/filter.py` once and then claimed completion without another visible tool action or test run; its two native tests failed. These observations are not attributed to memory reminders (none were delivered). Hidden test assertions were not inspected or exported.

Task usage fields recorded by the runtime (not a proxy): SQLite input 20,176, output 5,158, cache-creation 10,526, cache-read 142,133 tokens; HTML input 2,404, output 3,062, cache-creation 433, cache-read 5,294. Auxiliary successful-response usage, physical HTTP attempt count and monetary cost are unavailable; 36 is a **logical call** count, not a physical-request count. Native Task intervals were about 11 min 00 s and 1 min 32 s; verifier intervals about 57 s and 3 min 48 s, respectively.

## Private-original identity index

The following SHA-256 values identify original local bytes. The files remain in the private run directories; this report is a **summary projection**, not a byte-preserving or reserialized copy of them. In particular, the fake certification's byte-preserving `memory.json` rule was **not** applied to real data. Full visible requests, public response blocks, Task tool arguments/receipts, auxiliary request prompts, transport errors, final memory, and source state remain private for audit. Hidden thinking, credentials, private endpoints and hidden test sources are not published.

| Artifact | SQLite SHA-256 | HTML SHA-256 |
| --- | --- | --- |
| Prepared manifest | `895784614d70b2488cfcbc382a6fb30ddcc3e86d5b877a1a36144cd1c5929cae` | `7e977dc78ad71f54bb65e11b35a80fa3dc82bffc0bac7c86be619fbf4a701262` |
| One-use authorization before removal | `fe3ace50790c2b46138da47d556b2ab01cd8e2244e9e28cd8c5ddf7bfcd18635` | `c3a7453aac36057b0c9e4a07bda4bf845685d8b98a1631de89a5601fff086403` |
| `archive/live_result.json` | `f318f0f9de443e6b41ff84fd50c229845e37ce6204d62dcc770db0b10197bcf8` | `f3d7ec74041e298253c791c50da7d70dd3455e1f438b9a33bec4a7f2b77709f8` |
| Worker stderr (contains provider error) | `ad4974f58bdb3b3cb681e6e3e11eb2c13fb4a25cb9991b27cd0fb8fe356ed36f` | `0a216bac47161140f9ebeadc69d038e569b6a37e507448e76d68ea06009e8dcf` |
| Final `memory.json` | `167a33f1c83d84e59527e157d69994320dba954d4d6f56c63d7e5f1e66e0d417` | `167a33f1c83d84e59527e157d69994320dba954d4d6f56c63d7e5f1e66e0d417` |
| `gap_cycle.jsonl` | `4d599cfc532f0a7f30377549c939f44b5a202bb537ae1edd568e3d6be9f48cd0` | `0b1c6deb17a4cc84ea35a1a5e6be5923fbcc84667500e143821e24b892af15d0` |
| `memory_payload.jsonl` | `1dc8d005fc0f9a95f090f804df9ceec471a1ffc0b485d9ec18281ad52a9365de` | `042894e9201bb3f0f402726ea961eebb85fb646b2f908af3de8d833626b04460` |
| Task `research_events.jsonl` | `d7290798e34fe3521fe2f5ad429fa24f84ff271a353060ec64654616333d88d4` | `0a8153a882e804479621bc46a65cf2ab0ea2ad5b9b4a2cefe9cb8e15e361be2d` |
| Native CTRF report | `cd7d50f85fab309bf3434f7278301e6be5bf91ec983d79b4b5b26d09fb941aa6` | `9b036c0dcadfd18aa121fcea7c0897a6d88af6deec75415d4ee95c5bb4bbf9fc` |

Local-only config/catalog/plan/result SHA-256s are respectively `4e7d9b4a113808e7f53355c447ad37e454cf0ab88afeb1218499e0b8fd5f23f4`, `2e86b03eb03513bcffac6910e6b6c3bd2b83dbc4f1b1a86ddc86d2767536a4cf`, `ad028b9185bb05f3c631c8d9068106157becea7d65c20ca96ece1eca6bbd54ee`, and `4eeaab51c76c813134466759417c8d61156499f2e95162e802fe2650bb31c9ac`.

Both `live_result.json` files record `worker_return_code=0`, `cleanup_confirmed=true`, no remaining containers, and clean owned-volume clearance. `docker ps` showed no running containers afterward. Both one-use authorization files were removed and their absence checked. Old runs and certificates were not changed.

The external auxiliary billing denial requires a service/account decision before a meaningful real-model evidence-writing test. No key, provider, account permission, or balance was changed here. The current fail-soft PMA path allowed Task to continue through repeated auxiliary transport errors, so the native rewards must not be interpreted as a successful memory intervention.
