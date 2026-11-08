# Two new Task attempts with cached native evaluation

These are **new attempts**, not a reinterpretation or overwrite of the two missing-evaluation slots in the original five-task run. The original missing records remain in `PMA_SIMPLE_PROMPTS_8ED_FIVE_20261108.zip`.

Execution code: `c4557383cf61735a55f30d5a8a100d490ab50145`, based on `8ed3a7f8958db8c3f5807bd7276b9413d1d5f934`. The only production change is a prepared-dependency-bundle evaluation path in the unified runner and native verifier; the PMA prompts, wake cadence, tools, and Task agent method are unchanged. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Runtime policy: agent time and Task turns uncapped, official verifier timeouts.

| Task | New run ID | Native reward | Native tests | Cleanup |
|---|---|---:|---|---|
| rstan-to-pystan | `pma-a2c2030927614dff` | 1 | 6 passed, 0 failed | confirmed |
| filter-js-from-html | `pma-e41f8ed792a04cd4` | 0 | 0 passed, 2 failed | confirmed |

Each Task started once, then its official verifier started once. Both matched a task-specific, prebuilt `ga20-apt-uv-dependency-prototype-v1` bundle. The cached dependencies were restored **after the Task agent and writers stopped**; bundle readback, destination preflight, offline package readiness, and cleanup all succeeded. The official test script and scoring content were not changed. The results are cross-batch recovery observations because the evaluation dependency strategy and code SHA differ from the first five-slot run.

The ZIP provides complete redacted visible Task/PMA traces, actual runtime identities and effective policies, cache-stage receipts, official-test summaries, cleanup evidence, source-to-public hash mapping, and a per-file index. It is a public projection, not original HTTP bytes. Credentials, complete private profiles, private endpoints, provider-private thinking/signatures, hidden test bodies, and task workspaces are excluded. Private originals remain local.

Cached evaluator dependencies remove this particular `uv` download failure from these two verifier paths. They do not guarantee the Task, model service, or other dependencies will never need network access or encounter transport faults.
