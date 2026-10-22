# Stateful memory: native-tool interface reference

## Status and boundary

This is an **offline-tested reference component**, based on repository commit
`55560439a4b15afdc4573f2c6334f1ef91aa86f7`. It is not an enabled runtime mode,
not Harbor certification, and not evidence of model reliability or task benefit.
Only new files are added. Existing prompts, CycleEngine, provider, storage,
experiment_runner, authorization rules and current real runs are unchanged.

The purpose is to let the developer absorb tested compilers rather than invent
another schema/dispatcher. No real model, Task, token-count HTTP or evaluator
requests were made to build this reference.

## What was learned from PMA

Reference: yifannnwu/proactive-memory-agent at
`89e5c0d6aadfe531a1aee42fd290d48be89973dd`,
`src/memory_agent/memory/memory_agent.py` and `universal_memory.py`.
PMA exposes knowledge/procedural/status/delete tools, usually with just a content
or memory ID parameter; Python constructs records and serializes them. This
intent/representation split is borrowed, not claimed as direct code reuse.
No upstream code is copied into these new modules.

Do NOT copy PMA's immediate per-operation bank mutation, ignored unknown tools,
empty-content defaults, XML recovery, or treating absent output as normal no-op.
Those choices are incompatible with the existing candidate/audit/atomic commit
contract. Existing project validators are reused directly.

## Components and APIs

- `tool_native.py`: `normalize_claude_response(response,
  permitted_tool_names=..., response_complete=...)` returns detached `calls`,
  `tool_call_ids`, and visible text. Native input objects and strict JSON-string
  arguments are normalized; duplicate keys, non-finite/non-serializable values,
  unknown tools, duplicate IDs, incomplete responses and refusals are rejected.
  `validate_tool_arguments` is the shared validator for the exact schema subset
  emitted here, not a general JSON Schema implementation.
- `tool_maintenance.py`: `tool_definitions()` and
  `compile_maintenance(calls, binding=..., base=...)`. Thirteen typed tools cover
  knowledge, experiences, status transitions, entities, relations, requirements,
  gap creation/revision/closure/reopening, focus and explicit no-change.
- `tool_decisions.py`: `audit_tool_definitions()`,
  `selection_tool_definitions()`, `compile_audit(calls, view=...)`, and
  `compile_selection(calls, binding=...)`. One submit call per decision role.

All compilers are pure: they produce old-format objects, never write the Store,
execute Task tools, call a provider or mark a candidate committed. A bad item
rejects the entire batch. No partial result is returned as success.

## Model versus host responsibilities

The host restores protocol/request/base-version bindings and newly derived record
revisions. Audit closure resolution IDs expand against the exact supplied
resolve manifest. Selection bindings are supplied by the host; for this API pass
only state_version, task_version and phase2_view_id (the current payload also has
cycle_id, which is not part of the model decision object).

Models still select content, scope, provenance, supporting/challenging evidence,
record use status, historical task epochs, semantic timestamps, retirement and
closure reasons. Existing exact typed references and evidence quotes remain.
The proposed general short-handle registry is **not implemented in this slice**;
do not claim all IDs/revisions have disappeared. No BM25 or fuzzy reference repair
is allowed. Do not convert historical references to the newest version.

Semantic record fields remain richer than original PMA's content string. This
is not a claim that a tool magically turns arbitrary prose into valid state.

## Mandatory downstream gates

1. Freeze the original request, base, role, schema and visible input.
2. Receive the COMPLETE provider response; verify stream integrity upstream.
3. Normalize all calls against this request's permitted names.
4. Compile the complete batch, then run the existing domain gate:
   - maintenance: `validate_proposal` (also called by the compiler), then
     **`build_candidate` with SourceCatalog, visible_existing_ids, goal ledger
     and archive**;
   - audit: **`validate_audit_result` with the frozen view, catalog and archive**;
   - selection: **`validate_selection` with the committed snapshot and this
     request's selectable refs**, then existing rendering and delivery.
5. Only the original state machine may audit and atomically commit or deliver.

`base` means the retained full committed snapshot, not the projected before_view.
The model still sees only its allowed working set; build_candidate enforces that
visibility. Keep actual public tool responses and host-compiled internal JSON
as distinct artifacts. Do not describe host-restored bindings as model output.

Compiler success is NOT permission to commit. In particular, a valid literal
quote is not proof of semantic entailment. Entire required_coverage, including
unchanged retained claims, and all closure assessments remain mandatory.

Maintenance can have multiple tools in one completed response. `memory_no_change`
must be explicit and exclusive. Audit and selection each require exactly one
submit call. No-call output is not clean/silent. Audit unusable is not provider
refusal, and neither permits commit. Selection silent uses null refs and null
context_for_action at this new tool boundary and compiles to the old minimal
silent object.

## Actual integration still required (developer checklist)

Do not insert the old JSON-output system prompt unchanged into tool mode: it
would still ask the model to echo bindings and return a text JSON envelope.
Preserve semantic guidance, but change only output instructions and role tools.

The current StatefulRoleProvider only collects text blocks; CycleEngine._call
requires a string. Therefore adding schema definitions alone does not integrate
native tools. Adapt these existing seams rather than making a new HTTP client:

1. Use NativeClaudeSession's existing tools-to-native request path. Verify that
   the FINAL auxiliary payload really includes the role's tools/input_schema;
   an accepted SDK option or Task tool success alone is not proof.
2. Preserve tool_use blocks, stop reason and proven full-stream completion.
   The normalizer's `response_complete=True` is a caller assertion, NOT an SSE
   parser. Never set it unconditionally or infer it from having one tool block.
3. Preserve the call-attempt journal, request/schema hashes and no-blind-resend
   rule. Duplicate IDs in one batch are checked here; cross-request idempotency
   and unknown-outcome recovery still belong to the existing journal.
4. Route malformed model tool arguments/compiler errors into the existing
   model-validation/role-specific repair path, not a new automatic transport
   retry. Normalize NativeToolError to the appropriate ContractError at that
   seam. Refusal, truncation and transport failure remain distinct.
5. Audit correction keeps the exact candidate/view. Candidate repair replaces
   the whole rejected batch from the original base. Preserve the shared repair
   credit and selection's no-extra-repair policy; do not count each tool as a
   separate model turn or reset the credit.
6. Tool descriptors here are Chat Completions-style schemas, not proof of backend
   strict mode compatibility. Convert using the existing native adapter and
   validate its actual wire payload. Never silently downgrade to text extraction.
7. Include schema/tools in actual input-size and cost accounting, without
   re-enabling external token-count HTTP under the current off policy.
8. Keep legacy mode unchanged; freeze any eventual tool-mode configuration in
   the existing prepare/run identity. Do not alter an in-flight run.

The remaining runtime work is concrete and bounded: auxiliary request/response
plumbing, role-specific tool prompts, model-validation handoff, schema-inclusive
accounting, and source-bound native fake-wire/Harbor validation. General short
handles are a separate optional increment, not necessary to wire these compilers.

## Tests and claims

`test_tool_native.py`, `test_tool_maintenance.py`, `test_tool_decisions.py` and
`test_tool_pipeline.py` exercise real native-shaped message objects, actual
tool names, compiler equivalence and the old domain validators. The pipeline
test includes a forward-referenced multi-operation candidate and atomic rejection.
They do not send HTTP, parse real SSE, or certify the provider/Harbor integration.

Run from the repository root, using its existing Python dependencies:

```sh
python -m unittest \
  method_discovery.pma_stateful_memory_v1_20261021.test_tool_native \
  method_discovery.pma_stateful_memory_v1_20261021.test_tool_maintenance \
  method_discovery.pma_stateful_memory_v1_20261021.test_tool_decisions \
  method_discovery.pma_stateful_memory_v1_20261021.test_tool_pipeline -v

python -m unittest discover \
  -s method_discovery/pma_stateful_memory_v1_20261021 -t . -v
```

The whole package additionally uses the existing tiktoken/o200k_base dependency,
the pinned PMA BM25 file and already-committed historical fixtures. Do not alter
their hashes to make a partial checkout pass. Do not publish credentials, private
profiles or hidden reasoning with test output.

Completion of this reference is not authorization for a new model run. Follow
the user's applicable experiment authorization and preserve failed episodes.
