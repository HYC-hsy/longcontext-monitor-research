# PoS-on-GA native-SHARED: offline entry and future gate

This supersedes the older preparation-only `RUNNING.md`. The released PoS
vendor remains fixed at `luoyu100/PoS@6818cfa6434dbc91fcf67f0b3eb12a91db47433f`.
The four-task plan in `plan_four/plan.json` remains
`execution_authorized=false`. This document does not authorize a real run.

From the repository root, with Python 3.12+ and the already-installed GA
dependencies:

```
python -B method_discovery/pos_upstream_ga_v1_20261017/test_offline.py
python -B method_discovery/pos_upstream_ga_v1_20261017/test_ga_seam.py
python -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.test_single_run_offline
python -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.test_live_wiring
python -B -c "from pathlib import Path; from method_discovery.pos_upstream_ga_v1_20261017.certification import verify_evidence; print(verify_evidence(Path('method_discovery/pos_upstream_ga_v1_20261017/raw_v7')))"
```

The synthetic Harbor/Docker fixture needs the fixed clean Harbor checkout at
`459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`, the existing
`alexgshaw/db-wal-recovery:20251031` image and digest, the existing Linux
runtime mount, the pinned official source checkout, and a local private GA
profile. It uses a finite fake Task gateway and finite fake PoS role replies.
The profile is hashed/re-written to the local gateway, not contacted as a
provider. One complete offline command, with local paths supplied by the
operator, is:

```
python -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_fixture \
  --condition P --research-candidate PoS --task pos-synthetic-file-http \
  --output NEW_EMPTY_DIRECTORY --official-source-git FIXED_OFFICIAL_CHECKOUT \
  --task-profile-file PRIVATE_GA_PROFILE --ga-source GA_SOURCE \
  --runtime-root EXISTING_LINUX_RUNTIME --worker-python PYTHON \
  --harbor-python HARBOR_PYTHON --bench-root EXISTING_BENCH_ROOT \
  --harbor-source-root CLEAN_FIXED_HARBOR_CHECKOUT
```

This intentionally runs synthetic `code_run` calls, creates a marker file and
local HTTP service, then runs only the synthetic sentinel. It must not be
confused with a formal Task or official evaluator invocation.

For a future *separately authorized* real single run, the existing
`single_run prepare --condition P --research-candidate PoS` accepts one of
the four registered tasks and `--certification-dir` pointing at committed
`raw_v7`. It freezes the actual profile/source/vendor/config/task/evaluator
asset hashes and image identity. `single_run run` requires its existing
one-use authorization file with exact run/source/profile/config/task/budget
binding. The historical A/B authorization schema, an environment boolean,
or the synthetic flag cannot enable profile transport. No such real
authorization is created here; do not run the future command now.

PoS uses a fresh decision request with current observation and original
hybrid state view. GA native tools and termination remain authoritative.
One GA decision with its ordered tool batch is one PoS transition. Online
success stays unknown; `CURRENT_TASK_DONE` is not an evaluator verdict.
GA's public `<summary>` can remain in its Task output; it is distinct from
hidden native or tagged thinking. The actual GA system asset and callback
still contain summary-style wording, as the final-payload tests document.
