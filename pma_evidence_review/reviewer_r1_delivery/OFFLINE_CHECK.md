# Local narrow check (2026-10-31)

Parent code: `be44ce85fd2ec1ce116e34a8683cbcb7a113f35e`.
Worktree: independent `E:\pma-v4-reviewer-r1-1031`.
Interpreter: existing `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`.

Command: `python -X utf8 -B -m unittest pma_evidence_review.tests.test_claim_split_semantic pma_evidence_review.tests.test_reviewer_r1_compare -v`

Observed: 16 tests passed, 0 failed, 0 errored, 0 skipped (0.180 s).
`git diff --check`: clean. Both offline plan exports succeeded; no real model,
Task, native evaluation, or new split calls occurred.

Checks cover frozen A/B/claims/order identity across arms, only system text and
derived request hash differing, reference reasons excluded from model request,
single batch transport call, strict three-state result cardinality, overall/claim
aggregation, score identity, the retained v4 delete/repair paths, and exact
non-v4 maintenance system request. These are engineering checks, not reviewer
accuracy evidence. The old 13-case labels and nine constructed-control labels
remain frozen before any candidate result.
