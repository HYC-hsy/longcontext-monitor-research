# pos_pma_complement_v1: offline engineering boundary

This is a default-off research candidate, not a PoS/PMA paper reproduction or
an efficacy result. The PoS and PMA vendor trees are not edited. The independent
`PoS-citation-fixed` mode contains only the decoded-field citation fix; the
combination additionally changes method inputs and Task presentation.

| Category | Fixed source and original function | Local seam |
| --- | --- | --- |
| Direct PoS reuse | `belief/manager.py` initialization, `_build_candidate`, `_validate_candidate`, `_select_frontier`, progress/health/recovery; `belief/beliefSentinel.py` audit and scoring; `prompts/prompt_generation.py` | `pos_upstream_ga_v1_20261017/episode.py` still supplies actual joint-action transitions. |
| Direct PMA reuse | `memory_agent/memory/memory_agent.py` bank CRUD, Phase 2 parser and prompt builders; `universal_memory.py` bank and BM25; `trigger.py` | `memory_adapter.py` subclasses the original agent and keeps its bank/trigger objects. |
| Baseline repair, separate from candidate | PoS Sentinel `_trajectory_text` and `_valid_issue` | `pos_upstream_ga_v1_20261017/citation_fix.py` compares a quote within one decoded visible observation field, not joined serialized fields. Original mode remains selectable. This checks literal provenance, not semantic entailment. |
| Candidate method changes | PoS `_request_candidate`, `_refresh_belief_text`; PMA Phase 1/Phase 2 input and status availability | `candidate.py` supplies delivered suggestion as fallible revision context, deterministic committed-field text, and temporary Task panel. `memory_adapter.py` removes status from candidate schema/dispatch/rendering and appends PoS state only to Phase 2. |
| GA host adaptation | `GenericAgent-main/agent_loop.py`, `llmcore.py` | One actor tool batch is one PoS transition; only the current stateful Task request gets `system_overlay`. The GA history, native tools, termination and Task response policy remain in their normal paths. |
| Deployment adaptation | existing `single_run`, `offline_launcher`, `live_launcher`, `worker.py`, manifest/validator | Explicit method identity, staged fixed source bytes, finite fake PoS/PMA transport. Candidate profile transport is intentionally rejected before send and is not live-ready. |

Data order: original Task -> PoS reset -> first configured PMA wake -> Task
request with temporary panel -> accepted Task response -> real ordered tool
batch/receipt -> PoS candidate/audit/commit -> PMA trigger and two stages ->
next Task request. PMA Phase 1 sees original Task plus at most eight completed
actor steps; the revisable PoS state is appended only to Phase 2. One actor
step, not one tool, advances the PMA trigger. The original task and raw tool
receipts remain distinct from model state, bank prose and suggestions.

Delivery is logged only after the Task response has been completely accepted.
Preparation or a provider attempt alone is not delivery. A delivered suggestion
can inform the next *real* transition; it cannot modify PoS directly and is
cleared after that transition. The current gap/state panel appears even when
PMA is silent or not triggered. Its model labels are not external verification.

Panel, Phase 2 state and revision caps are respectively 16,000, 16,000 and
12,000 Unicode characters; at most four receipt excerpts of 2,000 characters
and eight directly referenced model-state records are selected. A required
goal/gap overflow is an error. Optional advice is dropped whole if it does
not fit; a clipped receipt is explicitly marked non-citable. These are
engineering limits, not token equivalence or an efficacy-tuned policy.

Failure matrix: a malformed PMA Phase 2 XML result becomes `format_rejected`
and no advice; a whole PMA transport failure propagates and stops the candidate;
a PoS semantic rejection retains the previously committed version; Task
transport failures remain Task failures; no auxiliary view can approve Task
completion. Worker/profile failure never silently changes the method to GA-only.
The fake tests prove wiring and authored fixture behavior, not model judgment.

Known incomplete points requiring separate review before a live candidate:
candidate PMA profile transport, exhaustive original-source provenance for old
bank entries, total provider token-budget measurement, and full Docker
native-SHARED certification. No live authorization is created by this package.
