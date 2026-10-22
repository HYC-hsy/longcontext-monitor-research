# GA-only SQLite unified-entry retry, 2026-10-22

This report is a public summary, not the private original Task/model transcript. It does not replace the prior HTTP 403 run or its audit.

## Identity and route

- Executed code commit: `66705fbba0771788f336884b433c9cb7dfe2372f`. This commit only added the previous access diagnosis after the source-bound A-only fake acceptance; runtime source files were unchanged.
- Run ID: `pma-1792c5ce7df34858` (the legacy carrier uses a `pma-` ID prefix even for condition `A` / candidate `U`). Fresh SQLite workspace and separate run root from the preceding failure.
- Same local real configuration, private Task profile and model `claude-opus-4-8`. Deployed Task profile SHA-256: `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`. No PoS, PMA or stateful auxiliary role was enabled.
- Fixed route: `experiment_runner catalog`, `plan`, `prepare`, then `run`, all with the same local configuration and a new selection directory. Prepared manifest SHA-256: `5ab7cde4f8267a8659db92909be26b4bfc6d3bc0962d6f6affdf0dface4ec3f8`; config SHA-256: `fc04ff4fed66a999bfea5fc56bb913b63e04932afd87d0fcc59bfaacb87499e3`.
- New one-use authorization original SHA-256: `6664bdd317021afb6cbdd23def92709b6ce6ae63016778d7c8cfb312324ac0da`. It was removed after termination. No fake fixture flag was active.
- GA-only legacy limits: maximum 300 Task turns and 14,400 seconds Agent wall time; native verifier limit remained 900 seconds. This is not an uncapped or original 900-second Agent protocol run.

## Observed outcome

- Task generation: 17 request attempts, 17 HTTP 200 responses; 17 accepted action selections, containing 16 tool-call IDs. The Task terminal record is `CURRENT_TASK_DONE`.
- The provider's previous `SUBSCRIPTION_NOT_FOUND` denial did not recur. No model, key, endpoint or code change was made between the two real attempts; the access condition changed outside this repository.
- Harbor controller return code 0. The native deterministic verifier ran once and recorded reward `1.0`. Agent phase: 2026-10-22 02:52:42–03:02:13 UTC; verifier: 03:02:30–03:04:03 UTC. A single-task result does not establish general method effectiveness.
- PMA finalization `not_enabled`; no auxiliary worker/call. `cleanup_confirmed=true`, `remaining_containers=[]`, `cleanup_errors=[]`, owned volume clearance `clean`. No identified run process remains. There was no additional episode or evaluation.

## Private originals and public boundary

The full original logs and model-visible content remain in the local run root `E:\ga-real-sqlite-retry-66705\01-sqlite-with-gcov-r1\runs\pma-1792c5ce7df34858`. They are not uploaded here. Original-byte SHA-256 values:

| Original artifact | SHA-256 |
|---|---|
| `archive/live_result.json` | `addc1e72d11dab76072e76cfa86e1daed3ce29d7b763a37c3afc02656a62a804` |
| `agent/research_events.jsonl` | `ea37fc31be63baa2482e8063b6986010a201432a26f0ca6ccbaff2900c9e7c69` |
| `agent/task_terminal.json` | `b136333f56ae75a841810c5760ae367db21d5d9e8793c0405c3a54a5a10ecbf7` |

This establishes the supported GA-only route through the unified entry and this one SQLite task. It does not establish that explicit runtime overrides or arbitrary model/dataset adapters are already supported for GA-only; see `README.md` for those boundaries.
