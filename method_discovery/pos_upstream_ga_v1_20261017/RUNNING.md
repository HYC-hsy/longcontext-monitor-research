# Released-core PoS-on-GA transfer: current stopping point

The only prepared comparison plan is `plan_four/plan.json`. Its four slots are
PoS-only and `execution_authorized=false`: nginx-request-logging,
adaptive-rejection-sampler, sqlite-with-gcov, write-compressor. They are
observed development tasks, not held-out tasks. Each future trial must begin
from the original instruction and a clean Task workspace, never a PMA bank.

The existing generic single-run CLI has an unarmed PoS plan command:

    python -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run prepare-pos --task nginx-request-logging --task adaptive-rejection-sampler --task sqlite-with-gcov --task write-compressor --output NEW_EMPTY_DIRECTORY --official-source-git FIXED_OFFICIAL_GIT_CHECKOUT --frozen-reference-manifest PRIOR_PUBLIC_MANIFEST_JSON

The same entry exposes `fake-pos`, an offline Harbor path with a finite fake
gateway, a finite fake PoS role reply file, and verification disabled. It is
not a real-model switch and was **not run** in this handoff. It refuses the
prepared four-task manifest before launch; its preparer would otherwise stage
an actual registered Task package and cross this turn's ban on new Task
experiments. It requires a synthetic public Task fixture and dedicated Harbor
lifecycle assertions before it may count as the requested H acceptance test.
The future fake command shape is:

    python -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run fake-pos --output PREPARED_PLAN_DIRECTORY --task SYNTHETIC_REGISTERED_TASK --run-root NEW_EMPTY_RUN_DIRECTORY --run-id UNIQUE_ID --pos-fake-replies FINITE_REPLIES_JSON --ga-source GA_SOURCE --runtime-root EXISTING_RUNTIME --task-profile-file EXISTING_PRIVATE_PROFILE --worker-python PYTHON --harbor-exe HARBOR --bench-root EXISTING_BENCH --official-source-git FIXED_OFFICIAL_GIT_CHECKOUT

There is deliberately no PoS `run`/live command yet. The old `run` command
still accepts only the old A/B authorization schema. Future live execution
requires independent authorization and a PoS-specific Harbor hook/identity
binding, artifact freeze, profile forwarding, failure cleanup, and H fake
acceptance first. Merely setting `GA_POS_LIVE_AUTHORIZED=1` is not an
authorization for an experiment. No four-task command should be executed now.

Local safe tests (no provider, Task, Docker, or evaluator call):

    C:\Python312\python.exe -B method_discovery/pos_upstream_ga_v1_20261017/test_offline.py
    C:\Users\hsy\AppData\Local\Temp\pma-ga-py312\Scripts\python.exe -B method_discovery/pos_upstream_ga_v1_20261017/test_ga_seam.py

The temporary Python paths above were used on the development host; they are
not public profile paths and need not exist elsewhere. Use Python 3.12 with
GA dependencies for the second test.

Methods: original `BeliefManager` owns initialization, candidate generation,
Sentinel audit/repair, commit, progress, health, recovery and textualization.
The wrapper maps one GA decision and ordered tool batch to one PoS transition.
Eight tools in one batch count once; K=8 means eight scored decision batches.
GA owns execution/termination. `CURRENT_TASK_DONE` is not hidden evaluator
success; `success_known=false` and task success remains unknown. The released
code's E/A persistence tie favors epistemic; its goal interpretation is fixed;
source labels and Sentinel quotes are not semantic proof. Recovery is advice,
not an execution or completion gate.

No real Task, PoS/PMA/provider, native evaluator, training or scoring-model
calls were made during this preparation. The audit TXT lists missing checks;
do not treat this as a completed live-ready integration or a PoS efficacy result.
