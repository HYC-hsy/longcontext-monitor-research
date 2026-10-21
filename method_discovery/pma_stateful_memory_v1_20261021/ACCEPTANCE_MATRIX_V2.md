# Core-contract repair V2: executed acceptance map

Spec `f57a7c47`; baseline `a2661f71`; tested code `87e09551`. Raw stdout,
stderr, commands, exit codes and SHA256 are in
[`evidence/core_contract_repair_v2/manifest.json`](evidence/core_contract_repair_v2/manifest.json).
“Passed” below means the named offline contract test executed; it does not
mean model semantic quality or full GA/Harbor certification.

| Item | Source and changed behavior | Executed counterexample/control | Remaining boundary |
| --- | --- | --- | --- |
| R1 | `retrieval._complete_bundle` → `engine._catalog`, `_select`: projected historical result now retains paired executed action, identity and truncation/unavailable marker; same `SourceCatalog` validates action EvidenceRef. Audit receives frozen catalog; selection re-retrieves and projects its own catalog. | `test_maintenance_catalog_carries_action_context`, `test_multi_tool_historical_context_keeps_pairing_and_truncation`, `test_missing_historical_action_is_visible_as_unknown_not_success`; actual provider messages inspected. Existing exact-ref/cache tests run. | No claim that action proves result or that truncated historical bytes can be restored. |
| R2 | `schema.validate_snapshot`: procedural lesson requires `inference` and `general_hypothesis`, without imposing that on all Knowledge. | `test_lesson_cannot_claim_tool_observation` includes direct and `build_candidate` checks; legal procedural and null-lesson controls in suite. | Semantic correctness of a legal conditional lesson remains model-dependent. |
| R3 | `store.archive`/`compare_and_swap`, `proposal.build_candidate`, `schema.requirement_ref`, `retrieval`, `projection`, `audit`, `engine._select`: typed exact Requirement history is archived atomically, closed gaps may retain verified old refs, open gaps require active current head, archive context is not promoted to selectable head. | `test_requirement_history_through_candidate_audit_commit`, `test_same_goal_interpretation_revision_migrates_open_gaps_atomically`, store rollback and continuous fake goal migration. Unknown old versions and stale open refs rejected. | Target-change examples are finite synthetic control cases, not a general proof of goal semantics. |
| R4 | `engine.run`, `_goal_context`, `_catalog`, `proposal.build_candidate`: frozen GoalLedger text/deltas/source identity and prefix position enter maintenance and audit; mandatory bytes counted; CAS checks current epoch; pending event frontier remains separate. | `test_goal_context_visible_without_advancing_pending_frontier`, `test_two_user_revisions_freeze_full_goal_ledger_but_not_frontier`, `test_required_goal_text_over_budget_fails_before_provider`, `test_new_goal_during_maintenance_cannot_commit_frozen_candidate`, prior audit-time revision regression. | No selection while frozen prefix leaves backlog; no hidden goal truncation/retry. |
| R5 | `proposal.validate_proposal`/`build_candidate`, `audit.validate_audit_result`: transition union, ref shape, nonempty reason and visible refs checked before applying; new declaration uses `@local`; Issue witnesses nonempty and invalid Issue makes audit unusable. | `test_transition_cannot_restore_active`, `test_transition_references_must_be_visible_and_valid`, existing malformed proposal/audit tests; `ScriptedProvider` now uses legal local declarations and real field witnesses. | The host does not decide whether a structurally valid issue is semantically right. |
| R6 | `reminder._selected`/`render_reminder`: time, origin, use_status, procedural episode/lesson and gap_kind preserved in host anchor. | `test_anchor_status_time_origin_and_gap_kind_table`, `test_procedural_episode_and_inference_lesson_render_separately`, `test_historical_knowledge_is_not_current_anchor`, whole-turn UTF-8 limit test. | Generated note remains explicitly advisory and may be wrong. |
| R7 | `prompts.MAINTENANCE_SYSTEM`, `AUDIT_SYSTEM`, `SELECTION_SYSTEM`: model-visible wire fields, unions, enums, reference/closure and strict silent/remind shapes expanded, with no protocol field in selection. Actual system text contributes to `TokenProxy.measure`. | `test_strict_request_contains_wire_contract_not_only_field_names`, `test_selection_prompt_declares_output_shapes`, plus actual engine requests and runtime validator accept/reject tests in 70-test run. | Prompt and validator are not generated from one schema; completeness is covered by these finite checks, not a formal equivalence proof. |
| R8 | `engine._counted`, `run`, `_select`, `budget.TokenProxy`, `reminder.attach_once`: result counts derive from journal phase rather than speculative `calls+1`; selection preflight adds no phantom call; candidate-only audit size can consume the shared single repair credit if complete repair input fits; unknown reminder send cannot be bypassed by cycle change. | `test_preselection_failure_counts_no_phantom_call`, `test_candidate_audit_budget_uses_only_shared_repair_credit`, post-commit pending regression, initial provider failure counts, reminder replay test and 3/4/5-call fake scenarios. | Observable attempts are fake transport starts; real network/response ambiguity awaits host integration. |

The continuous fake episode in `test_multiround_v2` covers initial empty state,
Knowledge + Procedural + open gap, reminder inclusion in a synthetic accepted
Task request, later contradictory observation, bounded issue/repair/reaudit,
target revision, exact Requirement archive, silent selection, and one later
synthetic action. It is a core FakeProvider/FakeTask chain, **not** a
single_run/Harbor/native-SHARED deployment test.

The GA13 development fixture reads only archived lines 52–53 for
`toolu_exwuJ8l8ii6K0TOkaI8jn6`; its new proposal/audit are synthetic. The
archived command is not run. The fixed observation is not a held-out model test.

Final run: 70/70 tests, zero failures/errors/skips; eight separate fake
scenarios; one continuous fake episode; one GA13 development fixture. The
first new pre-fix counterexample run was observed (5 failures, 1 error) but
its console bytes were not retained, so there is no claimed raw pre-fix log.
