# Scoped maintenance without semantic review, v1

Baseline: `e52908b1ca68b62e35ba8bec67ff106434503f4a`.
Explicit opt-in: existing `pma-gap-evidence` carrier plus
`memory_maintenance_policy: maintain-scoped-latest-no-review-v1`.
Do not supply `citation_review_gate` or `citation_review_strategy`.
Historical defaults are unchanged. This branch is an engineering candidate;
semantic error reduction, reminder usefulness and task reward remain unverified.

## Implementation and reuse

The candidate uses the existing LatestEvidenceGapMemory store and per-operation
parse/validate/atomic publication loop. Missing, malformed or non-exact optional
quotes retain their binding outcome; they do not trigger semantic rejection or
repair. Invalid content/targets and damaged source state still fail engineering
validation. Source alignment is not truth certification. There is no gate client,
claim splitter, batch reviewer, repair opportunity or shadow-review request.

The phase-2 code was moved without behavior changes into
`verbatim_selection_mixin.py`; both the old gated class and the new
MaintenanceNoReviewAgent use that same implementation. The tag protocol, TASK/Mn
aliases, pinned revision checks and exact text delivery are unchanged. The
candidate still receives the full task, existing bounded eight-step visible
window, and current bank through the existing host context builder. No pagination,
recall stage, new memory schema, confidence scores or additional model call exists.

The candidate prompt replaces conflicting inherited failure/output guidance in
its assembled system and replaces matching tool descriptions. It prioritizes
maintaining corresponding records, continued-work value, concise current status
and unresolved conditions, and preservation of scope, partial results and useful
failure history. Causes require support; plans, claims, self-printed success text,
observations and whole-task completion are distinguished. Existing test-quality
GAP guidance is retained. It adds no domain-specific SQLite rule or prescribed
cross-shell check. These are instructions, not deterministic semantic guarantees.

## Execution boundaries

The carrier name remains `pma_gap_evidence_v1`, retaining task assignment,
prepare_context, gap-cycle logs and transport phases. The policy is validated and
bound across frontend, single-plan, manifest, batch, launcher, Harbor spec and
worker readiness; a dropped policy fails rather than silently selecting the old
free-synthesis agent. Policy plus gate/strategy is invalid.

The no-gate policy has its own `maintenance_source_sha256`, using the real
EVIDENCE_GAP_SOURCE_FILES host inventory; verify_gate_sources validates that
inventory before its old no-gate early return. The inventory includes the new
agent, shared selector, policy/config, private-fault and tag-contract dependencies.
The gated source inventory includes the relocated selector too. Old fixture
`require_bound_gap_memory` remains a fixture certificate constraint and is not
called to reject runtime unbound writes.

## Acceptance status

Implementation has dedicated fake-client and dispatcher tests. Full regression
acceptance is in progress at this intermediate commit because existing source
identity tests require a committed clean checkout. See ACCEPTANCE.md in the final
delivery for actual results, limitations and local evidence hashes. No real LLM,
Task, native episode, evaluator or Docker run is part of this development task.

## External source rules adapted

SAM/Cabeza's [fixed summarizer source](https://github.com/qhjqhj00/cabeza/blob/ac23445a44b6c2eee586ab32f52c8cf98df8f8bf/src/cabeza/memory/summarizer.py#L18-L40)
informs retaining consequential tool results, attempts, partial findings,
unresolved questions and the distinction between established and tentative
information. No SAM runtime or retrieval framework is imported.

PAIR's fixed [first summary](https://github.com/GuanghuiMin/pair/blob/16946dd8e8e24b1ffdf195d82df59090ca3a60d0/prompts/appworld/prefix/first_summary.jinja)
and [update summary](https://github.com/GuanghuiMin/pair/blob/16946dd8e8e24b1ffdf195d82df59090ca3a60d0/prompts/appworld/prefix/update_summary.jinja)
inform preservation of task boundaries and avoiding unsupported promotion of
intermediate or uncertain work to completion. We do not copy their section schema,
credential-preservation or benchmark-specific action/verification instructions,
and do not run their optimizer. These sources contain general summarization
instructions; our per-entry maintenance, GAP and tool-output adaptation is local.
This work neither reproduces their full methods nor establishes generalization.
