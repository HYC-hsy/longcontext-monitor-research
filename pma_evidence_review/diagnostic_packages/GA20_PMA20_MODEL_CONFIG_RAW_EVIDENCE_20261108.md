# GA20 and b171 PMA20 model-configuration evidence

This is a new, read-only audit of **all 20 historical GA episodes and all 20 b171 PMA episodes**. No model, Task or verifier was run for this audit, and neither earlier experiment archive was changed. The ZIP retains client-side captured Task request structures and associated attempt/response/usage events, P1/P2 stage payloads and transport records, visible stage responses, run/slot identity, effective-policy records, and per-file original-to-public hashes. It also includes the exact projection and audit scripts.

## What the evidence actually establishes

Across all 40 Task episodes, the captured request objects explicitly include `model=claude-opus-4-8`, `max_tokens=64000`, and `thinking={"type":"adaptive"}`. `provider_usage` events record API mode `messages`. Neither `temperature` nor `top_p` is present in any captured Task request. The bound manifests declare Task `temperature=1`, but that is **a configuration declaration, not a captured request field or a proven server default**. There is no official or server-side default-value attestation in these originals.

GA Task records contain 719 prepared requests, 969 provider attempts/responses and 714 visible-content response records. PMA Task records contain 817 prepared requests, 824 provider attempts/responses and 817 visible-content response records. Prepared requests and attempts are preserved separately; the difference includes transport retries and must not be called additional Task episodes.

PMA has 286 P1 and 112 P2 stage payload records, corresponding transport records and visible responses. Both stages are bound to the same `claude_monitor_opus48` profile file (SHA-256 `cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1`); the recorded memory model name is `anthropic/claude-opus-4-8`. The profile declares `provider=anthropic`, `api_mode=messages`, adaptive thinking, `reasoning_effort=high`, `temperature=1` and `max_tokens=8192`. **The archived P1/P2 per-call stage payloads do not include model kwargs or a wire request, and do not log a client-object ID.** Thus the phases share a bound profile, but identical in-memory model instance and server-effective parameters are `unknown`. `top_p` is neither declared in this profile nor captured in the stage payloads.

The Task profile file SHA-256 is `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e` in both batches. The present local profile files match all 40 run-bound manifest hashes; the private originals are withheld. `MODEL_PARAMETER_EVIDENCE_INDEX.json` gives each task's run ID, model field provenance, request and stage counts, bound hashes, code commit, dataset and asset identity. Consult the per-task event/payload files to verify any row independently.

| # | Task | GA Task requests | PMA Task requests | P1 | P2 |
|---:|---|---:|---:|---:|---:|
| 01 | git-leak-recovery | 9 | 9 | 9 | 2 |
| 02 | git-multibranch | 20 | 21 | 5 | 3 |
| 03 | feal-linear-cryptanalysis | 36 | 80 | 23 | 10 |
| 04 | query-optimize | 10 | 5 | 5 | 1 |
| 05 | mcmc-sampling-stan | 21 | 22 | 9 | 3 |
| 06 | fix-ocaml-gc | 23 | 26 | 6 | 4 |
| 07 | rstan-to-pystan | 58 | 24 | 8 | 3 |
| 08 | merge-diff-arc-agi-task | 31 | 17 | 8 | 3 |
| 09 | break-filter-js-from-html | 19 | 5 | 4 | 1 |
| 10 | nginx-request-logging | 21 | 10 | 7 | 2 |
| 11 | circuit-fibsqrt | 176 | 21 | 9 | 3 |
| 12 | multi-source-data-merger | 15 | 14 | 4 | 2 |
| 13 | filter-js-from-html | 2 | 6 | 4 | 1 |
| 14 | largest-eigenval | 30 | 17 | 10 | 3 |
| 15 | make-mips-interpreter | 201 | 461 | 139 | 58 |
| 16 | kv-store-grpc | 12 | 17 | 3 | 3 |
| 17 | sanitize-git-repo | 2 | 8 | 7 | 1 |
| 18 | build-pov-ray | 4 | 17 | 8 | 3 |
| 19 | reshard-c4-data | 22 | 20 | 10 | 3 |
| 20 | db-wal-recovery | 7 | 17 | 8 | 3 |

The GA result is a cross-batch recovery: tasks 01–02 used code `84327f001c7a05c02983895894b122f37b3b9dcd`, 03–18 used `f8c10e23ddf96bd5b06860dac20bc3418124ed87`, and 19–20 used `e73a2b695bb820cc3119dc575d60b3d6aa04088b`. PMA used `b17151b8d57c61cfb4e058ad1601225f9fa2ea15` throughout. All 40 manifests bind dataset `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; their per-task image digest, public task tree, native test tree and verifier script identities match across batches. Their plans declare `agent_timeout=uncapped`, `task_turns=uncapped`, `verifier_timeout=official`, and per-run effective-policy records are supplied. The GA originals do not independently attest a native Harbor Git commit; the PMA batch was prepared against `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Different batch dates, code and PMA calls remain substantive differences. Equal captured client requests do not prove equal server behavior.

## Publication boundary

Twenty `pma_stage_transport_original.jsonl` files are byte-identical, safe original files. All other source-derived public files are explicitly marked projections. For each, `SOURCE_MAP.json` records the local source identity, original byte count/SHA-256, projection byte count/SHA-256 and whether bytes match. `MISSING_AND_WITHHELD.json` lists private originals and non-retained wire evidence. The external `.index.json` provides every ZIP member's size, SHA-256 and classification. The private run configurations, Task profile, full PMA profile, credentials/endpoints, provider-private thinking/signatures and hidden-test material remain local. Request `thinking` **configuration** is retained; private thinking **content** is excluded. The package is not a raw HTTP capture, and source hashes do not make a projection byte-identical to its original.
