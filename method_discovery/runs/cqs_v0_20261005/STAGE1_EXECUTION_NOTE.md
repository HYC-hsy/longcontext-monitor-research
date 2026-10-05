# CQS-v0 Stage-1 execution authorization

The main research thread authorized only two fresh candidate-only screening trials: S1 Fyne `07f7f2174a604dbbab124435d0677398`, then S2 Kitex `f74b27efdeff45cc96bf9b70dac8e97a`. The historical `STAGE1_PLAN.md` and `STAGE2_RULE.md` remain non-executing. This authorization is represented separately by `EXECUTION_AUTHORIZATION.json` and each slot's `AUTH_<run_id>.json`.

Frozen candidate: `cab01032c82d817b1b9ba28e18ef2504bd4a87a7`; frozen Stage-1 plan commit: `81fd1da117698913c9d16a6ac3ea6b9e4020d98b`; research execution adapter commit: `dd6b77ef7ec13872997a82692775f624ba57c857`. The generated `PLAN.json` SHA-256 is `27b3fb2829a4118f4f7bf407da5e579ffcb4dd2636d0a6cdc76b62a29f51dfcf`. The same new private CQS deployment/profile is used for both task slots. It copies the previously frozen DCM private deployment and overlays only the CQS implementation diff; model credentials stay private and are not archived here.

The slots will be run serially because shared local Docker/provider capacity and rate-limit independence cannot be mechanically guaranteed. S2 is not conditioned on S1's scientific result. Any confirmed identity/isolation leak or loss of critical trajectory/scored-artifact binding pauses the batch. Normal scientific outcomes do not cause rerun, patch, or early stop. No Stage-2 baseline is allocated or authorized.

Each run uses the existing runner and gateway/trial bridge, through `python -m method_discovery.uc_cqs_entry --run-id <id> --authorization <absolute AUTH path>`. The per-slot independent authorization and actual deployment hashes must pass before Harbor starts. Terminal capture/evaluator follows the existing bridge; hidden evaluation remains outside online control.
