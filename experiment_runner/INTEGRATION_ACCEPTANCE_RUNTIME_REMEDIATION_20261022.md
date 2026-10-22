# Config runner + stateful runtime remediation acceptance (2026-10-22)

This is a zero-model integration check, not a live episode or method-effect result.

- Merge parent: `b93cdf4fbe8e4d9ad09b9317f8f92022e79d7999`; accepted patch: `365aa7729aa02d7a846d3ab183881511dea10de9`.
- Integration commit: `d7b4c978b9695cc5a6b9865bed41b79bf38c084b`; subsequent bounded forwarding fixes: `4c32380278b747f123da3d2ea27546c32d96fa63`, `87fd52418f4e91def84a96b47bd2e4f070cd7327`.
- The public example now explicitly selects `native_context_policy=off` and `research_capture_policy=best_effort`. `experiment_runner` validates these values, includes them in its plan hash, forwards them to `single_run.prepare`, and rejects a driver plan/manifest that changes or omits them. The manifest includes both values before computing `config_sha256`.
- Local pinned dataset catalog and plan succeeded. The local private three-slot plan retained SQLite occurrence 1 followed by sampler occurrences 1 and 2; no slot was executed by this catalog/plan check. The example remains a single SQLite slot. No private profile contents are in this report.

## Offline tests

- `python -B -m unittest discover -s experiment_runner -t . -p test_*.py`: **63 passed, exit 0** under the local Python 3.13 test environment.
- The remediation handoff's combined pytest command, with repository and `GenericAgent-main` on `PYTHONPATH`: **192 passed, 226 subtests passed, exit 0**. This includes actual mocked Task/auxiliary policy propagation and capture-failure checks.
- The additional historical `test_single_run_offline.py` collection: 17 passed, 1 skipped, 2 failed. One old committed fixture's execution identity no longer matches new source bytes; another test patches a removed `run_selection.prepare` attribute. These are not counted as passing new-source certification and were not altered to hide the failures.
- An initial attempt with the Python 3.9 default failed collection on `int | None`; a Python 3.13 environment without `tiktoken` failed dependent tests. Final tests used the existing Python 3.13 environment with `pytest` and `tiktoken`.

## Source-bound same-run fake Harbor chain

Final execution code commit: `87fd52418f4e91def84a96b47bd2e4f070cd7327`.
Existing `single_run_fixture` prepared and invoked `single_run run` with the pinned SQLite task, B carrier, `pma_stateful_memory_v1`, `--service-fixture`, explicit uncapped Agent runtime policy, `--native-context-policy off`, and `--research-capture-policy best_effort`. Its isolated authorization was fake-only and removed afterward.

Final run ID: `pma-a513a17af7454705`. Controller exit 0; the source-bound public exporter/validator accepted 20 files and reports 54 source files, 8 host spool events and 2 actual fake Task requests. The host received initialize, prepare_task, agent_report, a real synthetic tool action_batch, the next prepare_task, confirm_task, agent_report and finish. The second Task request contained the tool result and one newly inserted reminder; counts were `[0, 1]`. Worker ready/exit both bound the same run and `off/best_effort`. No native-count archive was produced and the fake network boundary recorded two Task generation requests. This is **zero external token-count HTTP and zero real generation HTTP**.

The synthetic file/service verifier recorded reward 1.0 **only for the fake fixture**, after the writer stopped. Task terminal was `CURRENT_TASK_DONE`; worker return code 0, container/volume clearance clean, and fake authorization removed. No official task score is inferred.

Private raw fixture root: `E:\sf-merge-explicit-87fd52`. Public redacted export: `E:\sf-public-explicit-87fd52` (local, not a committed certification directory). `FILE_HASHES.json` SHA-256: `75490ca516e88cfdcbe2c9fce5524c633e4b228561a335807f662a94647eb48`. Raw execution identity SHA-256: `8fb0043801b5bb683e5d7e19c8a3871ff60d208ee5e77b4572ac1cff6973f2a5`. The export separately records raw/public hashes; its derived request summary is not raw request bytes.

Two earlier directories remain unchanged: `E:\sf-merge-d7b4` stopped before Harbor because the batch preflight omitted frozen policies from its spec; `E:\sf-merge-4c3238` reached the Task container, where the new policy environment variables had not been forwarded and initialize correctly failed. Neither is reported as successful certification. A third successful legacy diagnostic-time fixture (`E:\sf-merge-87fd52`) is distinct from the final explicit runtime-policy fixture.

The tested frontend and fake fixture do not authorize a real run. The new `off` policy deliberately has no native-token preflight; provider context rejection remains possible in a future separately authorized run. `best_effort` can leave research evidence gaps, while state journal, CAS, spool receipts, full-response validation and HTTP errors remain strict.
