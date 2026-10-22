# Configuration-runner merge acceptance (2026-10-22)

This is offline reception of patch `d74e1618cab0224d9f09bf5051fe4c02f42595e7` from `fix/config-driven-runner-parent-20261022`, merged into the continuing `crs-v0-20261007` branch. It is not a Harbor source-bound certification or permission for a real episode.

## Merge and limited compatibility edits

- The fetched patch SHA matched the requested SHA. A non-fast-forward, no-commit merge produced one content conflict, in `harbor_adapter.py`'s adapter byte pin. Both the existing stateful diagnostic identity alternative and the patch's new native-`None` adapter behavior were retained. The merged adapter bytes hash to `092394995b153dd173dba553c20ad4c25ef23300df72596507a51e52b6841d0e`, now the primary pin. No whole-file ours/theirs resolution was used.
- `test_runtime_integration.py` was adjusted only for the local Windows/Python environment: Windows reserves `AUX` even with `.json`, Git's POSIX shell is used for `sh -n` when not on PATH, and source is decoded explicitly as UTF-8. No assertion was removed.
- The already committed live `audit-result/2` validator/prompt and archived diagnostic remain unchanged. The other thread's count/capture/audit/proposal remedies were not implemented here.
- The incoming patch has blank-line-at-EOF warnings in several changed files under `git diff --check`; these were not mechanically rewritten because doing so would change pinned source bytes without a functional reason.

## Local validation

`python -B -m unittest discover -s experiment_runner -t . -p 'test_*.py' -v` with the machine's default Python 3.9 collected only 26 tests and failed to import four modules because the patch requires Python 3.11+ (`tomllib` and union types). This first attempt is not counted as passing.

With the existing Harbor Python 3.13 environment, the same discovery command ran **61 tests, 0 failures, 0 errors, 0 skips**, exit code 0. Raw local transcript: `E:\LongContext\experiment_runner_accept_20261022\unittest_final_transcript.txt`, SHA-256 `77bade9c5765b45e789691d03a6d2f6ebb3f4e62979207766b15013efefbeb83`. Tests use synthetic assets, fake backends/environment and no real model, Docker task or evaluator.

The private-path-only `experiment.local.json` remains local and untracked/ignored. Its final SHA-256 is `07a1dd0a8ea6a1f290e165b7cba30d111fff143f5ac9a8778f65a1d54d310424`; no profile contents were read by `catalog` or `plan`. The actual local pinned task source at `2fd12b88aafdd04a52c298e3940bcb189f9766d6` produced a catalog of 88 tasks. Catalog command exited 0; raw local `catalog.json` SHA-256 `2e86b03eb03513bcffac6910e6b6c3bd2b83dbc4f1b1a86ddc86d2767536a4cf`.

The plan command exited 0 and produced `ga-experiment-resolved-v1`, `execution_authorized=false`, plan identity `3fc19e0d8c87a356c8a4000c0a98e29052c6983322620ab5cb6f05a58c5d8041`. The three ordered slots came only from local JSON: SQLite occurrence 1, adaptive-rejection-sampler occurrence 1, then that sampler occurrence 2; each resolves to B / `pma_stateful_memory_v1`. The effective policy has no cumulative Agent seconds or Task turns, keeps the official verifier's 900 seconds, and labels this a diagnostic Agent override. Raw local `plan_valid_paths.json` SHA-256 `75860a401d20d2ea452419efbfe6768f4f088019a2d140668a3fe0fb80a9339a`.

The 61 tests include rejected unknown methods/tasks, stale configuration and authorization, prepared argument forwarding, serial stop-with-not-started behavior, output placement, environment restoration and runtime-policy binding. Those are finite fake/mocked driver checks, **not** a real Harbor prepare/run or new source-bound certification. No authorization was created or used.

## Support boundary and next integration point

The catalog accepts compatible pinned local Terminal-Bench task packages; the existing execution driver remains tied to its fixed official source commit. It is serial, selects registered existing methods, and supports explicit runtime policy only for `pma-stateful`. It is not an arbitrary dataset/model/plugin framework. Both profile paths remain required by the legacy driver, but this reception did not read their private contents.

The other thread's proposed count/capture and core-contract changes are not included in this merge. Their final parameter names and behavior must be reconciled in this frontend only after that separate patch arrives. A final-source Harbor full-fake chain and actual native-context/transport certification remain outstanding; this reception is intentionally not used to launch a real task.
