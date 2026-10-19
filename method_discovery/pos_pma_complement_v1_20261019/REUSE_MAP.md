# pos_pma_complement_v1: offline engineering boundary

This is a default-off research candidate, not a PoS/PMA paper reproduction or
an efficacy result. The PoS and PMA vendor trees are not edited. The independent
`PoS-citation-fixed` mode contains only the visible-tool-field citation fix; the
combination additionally changes method inputs and Task presentation.

| Category | Fixed source and original function | Local seam |
| --- | --- | --- |
| Direct PoS reuse | `belief/manager.py` initialization, `_build_candidate`, `_validate_candidate`, `_select_frontier`, progress/health/recovery; `belief/beliefSentinel.py` audit and scoring; `prompts/prompt_generation.py` | `pos_upstream_ga_v1_20261017/episode.py` still supplies actual joint-action transitions. |
| Direct PMA reuse | `memory_agent/memory/memory_agent.py` bank CRUD, Phase 2 parser and prompt builders; `universal_memory.py` bank and BM25; `trigger.py` | `memory_adapter.py` subclasses the original agent and keeps its bank/trigger objects. |
| Baseline repair, separate from candidate | PoS Sentinel `_trajectory_text` and `_valid_issue` | `pos_upstream_ga_v1_20261017/citation_fix.py` checks one actually displayed tool-return field or head/tail segment. Host `next_prompt`, arguments and advice confer no tool provenance; decoded text is not escape-decoded again. Original mode remains selectable. This checks literal provenance, not semantic entailment. |
| Candidate method changes | PoS `_request_candidate`, `_refresh_belief_text`; PMA Phase 1/Phase 2 input and status availability | `candidate.py` supplies delivered suggestion and bounded frozen old-source segments as fallible revision context, deterministic committed-field text, accepted-revision identity and temporary Task panel. `memory_adapter.py` removes status from candidate schema/dispatch/rendering, appends PoS state only to Phase 2, records actually rendered bank IDs and creation-time visible event IDs. |
| GA host adaptation | `GenericAgent-main/agent_loop.py`, `llmcore.py` | One actor tool batch is one PoS transition; only the current stateful Task request gets `system_overlay`. Candidate required host capture failure stops later sends; accepted Task terminal remains separate. Candidate-only complete serialized request byte cap is checked before POST. Candidate auxiliary PoS calls now use the existing strict parser's structural integrity evidence and a typed provider rejection without enabling Task response retries; U/GA and original PoS stay on their prior paths. |
| Deployment adaptation | existing `single_run`, `offline_launcher`, `live_launcher`, `worker.py`, manifest/validator, `event_spool.py` and new thin `candidate_transport_worker.py` | Explicit method identity and staged fixed source bytes. Host-only PMA profile loader/transport is the same pinned U adapter and LiteLLM retry implementation; candidate bank stays in PoS worker. Spool has one event ID per call, no automatic replay, fixed Task deadline, private host profile hash and explicit stop receipt. Candidate outer success now requires known-complete native archive status; this is comparison eligibility, not a Task terminal/evaluator gate. No live authorization exists. |

Data order: original Task -> PoS reset -> first configured PMA wake -> Task
request with temporary panel -> accepted Task response -> real ordered tool
batch/receipt -> PoS candidate/audit/commit -> PMA trigger and two stages ->
next Task request. PMA Phase 1 sees original Task plus at most eight completed
actor steps; the revisable PoS state is appended only to Phase 2. One actor
step, not one tool, advances the PMA trigger. The original task and raw tool
receipts remain distinct from model state, bank prose and suggestions.

Delivery is logged only after the Task response has been completely accepted.
Preparation or a provider attempt alone is not delivery. A delivered suggestion
can inform the next *real* transition; it cannot modify PoS directly and its
consumption cursor clears after that transition. An immutable delivered record
and actual consequence remain available to the next PMA Phase 2. The current gap/state panel appears even when
PMA is silent or not triggered. Its model labels are not external verification.

Panel, Phase 2 state and revision caps are respectively 16,000, 16,000 and
12,000 Unicode characters; at most four receipt excerpts of 2,000 characters
and eight directly referenced model-state records are selected. A required
goal/gap overflow is an error. Optional advice is dropped whole if it does
not fit; a clipped receipt is explicitly marked non-citable. These are
engineering limits, not token equivalence or an efficacy-tuned policy.
The adapter also caps each candidate complete serialized Task/PoS payload and
PMA role input at 90,000 UTF-8 bytes; the existing frozen `max_tokens` values
remain the separate output reservation. This is not a measured model-token
context guarantee. Required content that still exceeds the cap fails before
the HTTP boundary; ordinary Task history trimming retains its native pairing.
The effective GA `context_win` is a history-trimming heuristic (`3 * context_win`
characters), not a provider-certified token window. Candidate Task and PoS
budget telemetry records that value and each existing output reservation;
the PMA host ready receipt records its profile's value. If the profile lacks
an explicit provider context limit, the latter remains unknown rather than
being inferred from JSON bytes. The final provider payload and tools are
included in the serialized-byte guard, but byte count cannot certify fit in
an unreported provider token context.

Failure matrix: a malformed PMA Phase 2 XML result becomes `format_rejected`
and no advice; a whole PMA transport failure propagates and stops the candidate;
a PoS semantic rejection retains the previously committed version; candidate
PoS HTTP/transport, cancellation, incomplete-stream and required-capture
failures are typed and never passed to JSON correction; complete malformed
model JSON still receives the original finite correction. Task
transport failures remain Task failures; no auxiliary view can approve Task
completion. Worker/profile failure never silently changes the method to GA-only.
The fake tests prove wiring and authored fixture behavior, not model judgment.

Known incomplete points requiring separate review before a live candidate:
legacy bank entries have unknown source coordinates; creation-time visibility
is not sentence-level support; exact provider token-context measurement is not
available; real provider behavior and formal-task effects are untested. New
profile transport is only fake-last-hop validated, including an independent
host worker subprocess and a separately packaged PoS Docker worker. Their
combined single_run/Harbor profile-mode path is not yet certified. No live
authorization is created by this package.
