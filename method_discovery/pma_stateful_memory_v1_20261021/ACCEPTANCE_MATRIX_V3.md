# V3 offline acceptance map

Tested source: `df2e0f8acc3f41be44d6bfd4a06341a264eee953`. Exact commands, process exit codes, stdout/stderr, and hashes: [`evidence/core_contract_closure_v3/manifest.json`](evidence/core_contract_closure_v3/manifest.json). “Passed” below means the named offline test executed, not model semantic correctness.

| Item | Source/function and prior gap | Executed counterexample and legal control | Status / remaining boundary |
| --- | --- | --- | --- |
| F1 exact stored refs | `retrieval.visible_stored_source_refs`, `engine._catalog`; current G and retirement refs were missed | `test_current_requirement_exact_alias_reused_through_revision`, `test_retirement_alias_and_old_state_selection_context`, `test_exact_alias_matrix_in_three_real_role_messages`; existing source resolver tests reject wrong/unseen quotes | Implemented; exact stored spans registered only from frozen visible typed objects. Not every type × role pair is separately executed. |
| F2 historical State | `engine._contextual_objects`, `_select`; selected old State vanished after maintenance/audit | `test_historical_state_cannot_be_selected_as_current_head`, `test_historical_context_counts_toward_selection_budget` | Implemented; old body shown, not selectable as head; budget failure explicit. |
| F3 role-local exchange contract | `prompts.py`; audit had referenced types defined only for maintenance | `test_each_actual_role_message_contains_its_wire_type_closure`; `test_audit_closure` covers environment/goal_changed/merged_into basis; existing contract/engine validation suite | Implemented for tested shapes. Prompt text and validator are not one generated schema; model compliance unverified. |
| F4 transition rationale | `proposal.build_candidate`, `engine._operation_index`, `store.compare_and_swap/version_changes/state_version_change`; reason was not durable | `test_transition_reason_survives_restart_and_commit_identity`, `test_transition_version_record_rolls_back_with_commit`; ordinary commits in store suite | Implemented; metadata in audit and atomic persistent version record. Direct store call is not request-visibility proof. |
| C1 retirement timing | `schema.validate_requirement_retirement_transition`, proposal and store calls; exact old replacement could be rejected after head advanced | `test_committed_retirement_keeps_exact_old_replacement` and goal-change follow-up; current/obsolete replacement and missing history negatives | Implemented bounded clarification; fixed normative spec untouched. |
| E1 raw response size | `test_multiround_v2.FiniteProvider.__call__`; double JSON encoding inflated old size metric | `test_response_measurement_uses_returned_string_not_json_wrapper` with quotes, backslash, newline, Chinese; actual multi-round output | Implemented; V2 sizes unchanged, V3 raw string sizes measured. |
| E2 GA13 development | `test_ga13_dev_fixture_v3`; old fixture established archive import only | `test_real_observation_developer_states_and_semantic_blind_spot` uses read-only archived GA13 action/result and authored candidate/gold | Implemented control-path test, not historical-state replay or semantic model proof. |

## Cross-object / role boundary

| Object or edge | Maintenance | Audit | Selection | Qualification |
| --- | --- | --- | --- | --- |
| Current Requirement and exact stored refs | Frozen visible G | Frozen candidate/before plus exact aliases | Re-retrieved committed current head | F1 message test; selected ref can be current active only. |
| Historical Requirement, including retirement replacement | Context from selected workset | Contextual object, not candidate head | Explicit historical context | C1 multi-epoch and F1 alias tests; cannot be selected as current. |
| Current/historical State | Current W and selected old State | Candidate head plus contextual old State | Current head plus contextual old State | F2 test confirms old State body and rejection as selected ref. |
| Knowledge / Procedural | Selected bundles | Candidate and contextual workset | Re-retrieved committed bundles | Existing V2 engine/retrieval tests; V3 did not exhaust every subfield. |
| Open/closed gap and closure evidence | Current gap context | Gap changes, closure assessment and exact evidence aliases | Eligible open current gap; closed gap context only | F1 alias test and audit closure union tests. |
| New/revised/retired Requirement | Frozen GoalLedger and base | Proposed change and transition check | Only committed eligible head | C1 test preserves retired historical link; old replacement cannot be newly used. |

Exact stored alias and historical context are separate: a visible old object is not automatically a currently selectable reminder target. Repeated short text at two offsets retains distinct span identities. Display overlap has not been globally deduplicated. `required_coverage` remains about candidate current objects, not historical contextual objects.

## Actual offline runs

- Package discovery: 82 passed, 0 failures, 0 errors, 0 skips.
- V3-specific: 9 passed; GA13 V3: 1 passed; continuous episode: 2 passed. These are subsets of the discovery total, not additional unique tests.
- Eight standalone fake scenarios plus continuous fake episode; the latter observed 14 role calls/14 fake attempts and two synthetic Task tool actions. They are not provider attempts or a combined effect sample.
- Real model/API, real Task, official evaluator, network token-count: 0. GA/Harbor and native context guard: not executed.

Prior V1/V2 evidence was not overwritten. V3 raw files have per-file byte counts and SHA256 in the manifest. No raw provider secrets, private endpoint, or hidden thinking were used in these fake fixtures.
