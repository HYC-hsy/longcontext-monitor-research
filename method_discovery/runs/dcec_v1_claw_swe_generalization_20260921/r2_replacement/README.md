# Public R2 replacement archive

This directory contains the public-safe raw artifacts for the single frozen
DCEC-v1 CLAW-SWE generalization run:

`dcec-v1-generalization-claw-swe-sphinx8551-r2-replacement`

The official SWE-bench result is unresolved: the patch applied, 32
PASS_TO_PASS tests passed, and the target FAIL_TO_PASS test
`tests/test_domain_py.py::test_info_field_list` failed.

Included:

- Task Agent prompt, output, public research events, usage metadata and patch;
- Supervisor dialogue, transport/progress logs, History, working state,
  interventions, receipts and public task evidence;
- filtered OTel proof and frozen run/model/image identities;
- metadata for the two root checkpoints, excluding copied workspace trees;
- official verifier script, patch, output, report and run log;
- launcher and gateway logs.

Excluded:

- isolated bundles, credentials, CA material and local model configuration;
- duplicated task-view workspace copies and checkpoint workspace snapshots.

The factual analysis is in
`method_discovery/docs/DCEC_V1_CLAW_SWE_GENERALIZATION_R2_FACT_SUMMARY_20260922.md`.
