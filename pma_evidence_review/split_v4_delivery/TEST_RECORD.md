# Local offline verification (2026-10-31)

- Execution worktree based on `3f607a37335433126bf8cfbf40613c169902bfb0`;
  Python `E:/LongContext/bench_runtime/m4/harbor-env/Scripts/python.exe`, UTF-8,
  pinned PMA/vendor Harbor paths set in `PYTHONPATH`. No provider, Task, Docker
  lifecycle or native evaluator was started.
- Focused release command: `python -X utf8 -B -m unittest`
  `test_claim_split_semantic test_claim_split_simple test_claim_split_live`
  `test_simple_split_commit test_simple_split_bindings`
  `test_simple_split_pipeline test_live_gate test_claim_split_policy -v`
  (all modules under `pma_evidence_review.tests`). Actual exit 0, **78 passed,
  0 failed/error/skipped**. The diagnostic ZIP contains exact captured stdout and
  stderr, including scripted expected exception traces printed by the host.
- Both offline small-sample exports succeeded and contain 13 entries with equal
  material hashes. The v4 split model payload has no B; the v3 plan marks the
  two new deletion controls `not_applicable_delete_v3`.
- An additional `test_gate_policy_preflight` probe encountered a *pre-existing*
  fixture issue: `test_a_keeps_no_policy_and_rejects_gap_policy_override`
  supplies an `args` SimpleNamespace without `official_source_git`, whereas
  `single_run.prepare` requires it. The identical test fails identically in
  untouched baseline worktree `E:/pma-v3-offline30` at the same SHA. This is
  outside the changed v4 path; it was not fixed or counted as passing.
- Fake judgments and test controls prove protocol/atomic publication only. No
  claim about semantic model improvement, recall, accuracy or Task reward follows.
