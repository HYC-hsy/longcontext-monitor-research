# Host selection-context source closure

Base: `e278cd9abffee938846dff032019ca7702339655`.

The previous delivery omitted its new host renderer from two source-identity
lists. Add only `selection_context.py` to:

- `single_run_certification.EVIDENCE_GAP_SOURCE_FILES`, collected by
  `source_identity`, consumed by `prepare_six_task_manifest`, and checked by
  `live_launcher` (the evidence-PMA expected source set).
- `citation_gate_config.gate_source_paths`, frozen into the gate manifest and
  verified by `live_launcher` before its worker launch.

The host worker runs from STAGE. This does not add the renderer or audit packages
to the minimal GA container imports. P2/reviewer/prompt bytes and exact-byte hash
policy are unchanged. `source_identity.json` records precise baseline Git blob
and final SHA256 identities. Production diff is two list entries only.

## Verification (no model, Task, Docker or evaluation)

```
python -m unittest pma_evidence_review.tests.test_selection_deployment -v
python -m pma_evidence_review.gap_io_cleanup_delivery.run_offline_checks
```

- New tests: baseline 0/2, patched 2/2. Source collection executes the actual
  production list expressions and hashing functions via AST isolation (to avoid
  importing live launcher integrations). A temporary synthetic Git checkout is
  collected with the actual source_identity function and copied byte-for-byte;
  the new host file is included exactly once. This is not a live launcher run.
- Gate identity: real gate_source_paths/verify_gate_sources accept the complete
  manifest; missing entry, changed bytes (including newline bytes), and missing
  source file fail. No newline normalization is added.
- Original combined suite: 61/61, with explicit regex/shortuuid/Harbor optional
  dependency doubles in this cloud environment, and its pre-existing single
  frozen-dataset exclusion. This is separate from the user's previously reported
  strict e278 result with no doubles; a new strict deployment pass remains for
  the production environment. Logs are adjacent.

For independent acceptance, create a fresh checkout with `core.autocrlf=false`
and verify actual execution-file bytes against the frozen source hashes. Do not
change global Git settings or relax hashes to accept checkout conversion. Run the
original suite with `PMA_TEST_STRICT_IMPORTS=1`, plus the two new deployment tests.
No existing manifest should silently inherit the changed source identity; prepare
new identity artifacts through the normal authorized workflow before any future
real run. Real inference/Task execution remains separately authorized.
