# v4 narrow repair record

Code commit: `be44ce85fd2ec1ce116e34a8683cbcb7a113f35e`.
Parent v4 implementation: `29b54922978f9c080834933c83d46fcb586ff049`.

- A malformed split or batch response for `memory_delete` now quotes the
  submitted deletion reason in its operation-local technical error; it no
  longer reads the nonexistent `content` key. One-repair limit, gap retention,
  and processing of independent following operations are exercised.
- A malformed deletion evidence list or element is recorded as
  `citation_set_not_eligible` for that operation. The visible source catalog
  is still integrity-checked before this downgrade; source corruption remains
  a host error and stops subsequent operations.
- Non-v4 maintenance system text matches the pre-v4 gate baseline exactly.
  The new quote and gap-delete instructions remain v4-only.
- `REUSE.md` upstream anchors were checked against the fixed source files:
  EEA `checker.py` (1,239 lines), FActScore `atomic_facts.py` (317 lines),
  Sourcecheck `test_adversarial.py` (96 lines).

Focused local test: `python -X utf8 -B -m unittest
pma_evidence_review.tests.test_claim_split_semantic
pma_evidence_review.tests.test_live_gate -q` with the existing Python 3.13.14
environment: **41 tests passed, 0 failed, 0 skipped**. Expected exception
traces from synthetic fault-injection cases appear in the output; the command
exit code was 0. No full regression, fake lifecycle, model call, Task, or
native evaluation was run for this repair. The small-sample A/B in `README.md`
remains unexecuted and needs separate real-run authorization.
