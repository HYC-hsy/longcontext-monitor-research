# Fixed v1 checklist → implementation → offline evidence

Authority: `spec/REVIEW_AND_ACCEPTANCE_CHECKLIST_V1.txt` at
`f57a7c47a6b9a5d1c3911b886742e6627f625e76`. This is a scoped audit, not
a claim that the whole specification is accepted.

| Checklist | Implemented path | Executed check / remaining gap |
| --- | --- | --- |
| 1. State schema | `schema.validate_snapshot` | `test_contracts`, `test_schema_advanced`; migration combinations incomplete. |
| 2. Sources and evidence | `source.SourceCatalog` | Unicode, exact span, ambiguity, purpose, role, visibility and cache in `test_contracts`; no live host provenance. |
| 3. Workset | `retrieval.WorksetBuilder`, `projection.project_snapshot` | `test_retrieval`, `test_projection`, backlog test; complete optional/mandatory matrix unverified. |
| 4. Reversible audit codec | `audit.AuditCodec` | Reconstruction, order/hash, archive witness and reduced representation in `test_audit`; no provider semantics proof. |
| 5. Proposal/transaction/goal | `proposal.build_candidate`, `store.MemoryStore` | Original-base application, CAS, journal lookup, atomic multi-tool event and rollback in `test_proposal`, `test_store`; full goal migration matrix unverified. |
| 6. AuditResult | `audit.validate_audit_result` | Clean/issues/unusable, mixed-invalid and closure basis in `test_audit`, `test_audit_closure`. |
| 7. Calls/repair | `engine.CycleEngine.run` | 3/4/5 fake-call paths, one maintenance correction, same-trigger idempotency in `test_engine`; no live transport. |
| 8. Pending/frontier | `store`, `retrieval`, `engine` | Failed prefix replay, original event identity, backlog skip selection, atomic batch, budget-related backlog in tests and fake chain. |
| 9. Selection/delivery | `reminder`, `engine._select` | Strict silent/remind, stale goal, idempotent FakeTask delivery, postcommit failure in `test_reminder`, `test_engine`. |
| 10. Index/review marking | `retrieval.MemoryIndex`, `engine._select` | Postcommit index rebuild and reviewed/not-reviewed projection in tests; all archive-linked cases unverified. |
| 11. Full fake chain | `offline_fixture` | Eight finite method-local scenarios, 27 fake role calls, eight synthetic FakeTask actions; **not** `single_run`/Harbor/Docker or source-bound certification. |
| 12. New input count | `budget.TokenProxy`, real package message builders | Each fake call records chars, UTF-8 bytes and o200k_base proxy tokens in `FAKE_CHAIN_FINAL.jsonl`; no provider usage/cost. |

All 43 focused tests passed in `evidence/TEST_OUTPUT_POST_EXTRA.txt`. Test
fixture conclusions are scripted; a valid but wrong audit `clean` can still
commit a wrong state and a source-valid reminder can overstate its implication.
There was no real model, Task, official evaluator, training or scoring-model
call. No new active authorization or live entry was made. The absent GA host
adapter and native context guard prevent requesting a real experiment on this
evidence alone.
