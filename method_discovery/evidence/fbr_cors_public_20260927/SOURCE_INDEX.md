# FBR CORS public evidence package

Status: archival material only. No task, benchmark, evaluator, or model was
run while assembling this package.

## Source identity

Task: `roadmapbench:fbr-2.43.0-roadmap`.

The public task text is copied byte-for-byte from:

`method_discovery/artifacts/stage6d/stage6d-fbr243-shadow-v2/lineage_shadow/runtime_bundle/public_task.txt`

The public task contains seven targets. Target 4 is the CORS wildcard
requirement; this package does not promote Target 4 into whole-task evidence.

The checkpoint source is:

`method_discovery/artifacts/stage6d/stage6d-fbr243-checkpoint-parent-v1/frozen_checkpoint/`

The copied `checkpoint_parent/cors.go` is the frozen source at that checkpoint.
The copied state files are the available checkpoint metadata; no missing
working-state or tool receipt is reconstructed.

## Defect and correct-state evidence

The defect observation is available in the public R2 audit and checkpoint
source: the credentials branch retained request-origin echoing rather than the
literal wildcard required by the public Target 4 text.

The public corrected branch/result is available in:

`method_discovery/artifacts/stage6d/stage-r2-presentation-live-v1/i0/branch_bundle/`

and the valid R1 evidence-reconcile run is copied under `trajectory/r1/`.
The copied result reports the native Phase 4 CORS outcome; it is a historical
result, not a new measurement here.

The previously cited
`method_discovery/docs/STAGE6D_F1_FAILURE_CAUSE_ANALYSIS_20260820.md` is absent
from the current checkout and is not reconstructed.
`PMA_NATIVE_FBR_R2_AUDIT_20260912.md` is retained as a failure audit only; it
is not used as correct-state evidence.

## Copied files and hashes

See `source_manifest.json` for byte hashes, origin paths, and availability
classification. `available_copied` means the bytes were found and copied;
`historical_missing` means a cited source was not present; `planned` sources
are not included.

## Measurement status

The historical R1 run contains actual agent/tool/verifier artifacts under
`trajectory/r1/`. It does not provide a frozen paired preferred/unavailable
measurement design. D2 paired measurement materialization remains planned;
this package contains no fabricated receipt, output, or PASS label.
