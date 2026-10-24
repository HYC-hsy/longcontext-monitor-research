# Evidence interface repair v1: implementation and local handoff

## Scope

This patch repairs the existing opt-in `pma-gap-evidence` / `pma_gap_evidence_v1` candidate. It does not add a method name, role, model call, evaluator, or new launcher. Original PMA and `pma-gap` remain unchanged. Both phases and the Phase 2 prompt/parser are retained. Real runs are not authorized by this patch.

The observed development traces are `pma-e8b1699a9e2b4a43` and `pma-ee5cd9d22ff34012`, public archive commit `016984a9f6f24d0fb1d330fd17feb8b3dd14c926`. These are development evidence, not held-out tests.

## Function-level reuse, not a claim of wholesale upstream reuse

| Existing code | Concrete adopted behavior | Local destination | Boundary |
|---|---|---|---|
| This repository `episode.py` at base commit, lines 360–374 | Decode the known GA tool-result JSON envelope once; whitelist stdout/stderr/msg/output strings | `evidence_gap_context._project_tool_text` | Adapted existing logic; old candidate path not changed |
| `GenericAgent-main/agent_loop.py`, lines 393–394 and 615–616; `ga.py` code_run/file_write | Actual `{tool_name,args,id}` wire format and known code/script/content fields | `_project_tool_text` command branch | Does not heuristically decode arbitrary text or unknown tools |
| Pinned PMA `89e5c0d6aadfe531a1aee42fd290d48be89973dd`, `src/memory_agent/memory/memory_agent.py:480–513` | Ordered per-tool execution, retain earlier successes, record errors and continue | `EvidenceGapMemoryAgent._execute_tool_calls` | Adapted; argument extraction moved inside each protected operation, unlike upstream |
| Same pinned PMA `_extract_tool_call`, `process`; existing GapMemoryAgent | Tool argument extraction and maintenance→selection orchestration | Inherited calls | Direct reuse, no vendor edits |
| Current evidence store draft/publication and exact binder | Verify first; publish one complete operation; retain old value on failure | `_operation_draft`, `_apply_operation`, `apply_bound_write` | Existing machinery narrowed from whole-cycle to per-operation boundary |
| OpenWiki `305599f8e44203f9ca6b74bb6b38eebaf0b0405e`, `src/claims/core/mutations.ts:45–128` | Updates retain claim ID, validate proposed evidence before mutation | Stable-ID write adaptation | Concept/contract adaptation, NOT copied TypeScript or the whole-page batch transaction |
| LangExtract `3a68580f0aede0e96a2e1e03daa2a5f4011e4fcd`, `annotation.py:370–431` | Prompt and alignment consume the same source text | Source projection + literal binder contract | No runtime dependency; token MATCH_EXACT is not our character-exact test |

New local glue is explicit: JSON member-span offsets via stdlib JSONDecoder, immutable decoded-field parent binding, display-ID aliasing, stable revision links, safe per-item parser isolation and diagnostics. These are not described as upstream implementations. Graphiti adds no runtime code here.

## Model-visible contract

- Existing five tools remain. The four writers still require content and evidence; `memory_delete` takes memory_id only.
- Each existing memory has one visible ID. Use it for evidence.source, deletion, or in-place update. The internal revision/source identity remains immutable but is not a second ID the model must choose.
- `memory_save_knowledge`, `memory_save_procedural`, and `memory_save_gap` optionally accept memory_id to revise an existing record of the same category. Omitting it adds a record. Status remains its existing singleton update tool.
- Use the in-place update form to replace a record. Do not model a dependent replacement as a successful delete followed by a potentially failing save.
- Original observations are separately identified read-only sources; they cannot be deleted as memory. Memory references are derived-memory references, not independent observations.
- Citation resolves against the fixed pre-cycle view. Updating/deleting a memory does not change what an earlier citation meant or destroy its historical evidence.
- Quotes remain exact, contiguous and unique within the displayed source. No fuzzy matching, blanket newline replacement, guessed source reassignment or automatic acceptance of an unquoted conclusion.

## Text projection

Known tool fields are decoded exactly once before model input. The same decoded text is registered and used for citation matching. Child coordinates are positions in that decoded field, not raw HTTP/JSON offsets. Original envelope, field path, event identity and tool-call identity remain linked internally.

Raw wrappers keep literal non-body spans (status, exit code and other metadata), while decoded bodies appear once. Omitted regions cannot be cited across. Unknown/malformed wrappers stay literal rather than being guessed or recursively decoded. A literal backslash-n inside code remains a literal backslash-n after the appropriate single JSON decode.

## Operation failure semantics

Every operation has a separate parameter parse, validation, draft and publication boundary. A failed independent operation does not undo successful siblings. A single update is still atomic: invalid new content, reference, target or publication leaves its old record untouched.

Malformed nested XML calls are rejected as one malformed region, never executed as salvaged inner actions. Separately delimited valid siblings may continue. Nonempty canonical structured tool calls retain precedence over prose/XML fallback.

Cycle reports retain `accepted` (all operations succeeded), and add `partial_success`, `succeeded`, `failed`, plus indexed operation outcomes. An empty no-op is not a memory write. Downstream analyses must not label a mixed cycle as wholly rolled back, nor call every accepted no-op a successful write.

The next Phase 1 receives a compact, non-evidence diagnostic for failed operations. Only safe static codes/names are rendered; arbitrary exception bodies are not fed back. No extra model request or same-cycle repair loop is introduced. Phase 2 continues with the actual committed bank and existing recent trajectory.

## Offline replay interpretation

`evidence_interface_repair_v1_offline/REAL_REPLAY_REPORT.md` and the scripts in that directory preserve the actual public quotes and source provenance. The replay compares the pinned baseline binder with the new projector/binder. It explicitly selects the corresponding decoded field and its new ID; it does NOT claim unchanged historical responses pass a changed API or that real models will select those IDs correctly.

32 observed problematic references: 29 absent / 3 ambiguous under the old representation; 26 exact matches after explicit decoded-field selection, 3 absent / 3 ambiguous remain rejected. Noncontiguous quotes, wrong-source selection and repeated matches are not relaxed. These are reference-level development results, not 26 successful Task operations or new task scores.

## Developer acceptance, no redesign

1. Fetch and merge the delivered branch/SHA without force or resetting unrelated work. Read this file and the offline acceptance report.
2. Use your existing Windows Python 3.13.14, pinned PMA/Harbor imports and installed dependencies. This patch does not require switching to the cloud test interpreter.
3. Run `test_gap*.py`, `experiment_runner` and the four affected GA seam/parity/complete-response test files using existing commands. Use the existing `evidence_requirements.txt`; no new dependency was added by this repair.
4. Re-run the real-evidence replay and inspect valid operation persistence, in-place update failure preserving old value, all three gap classes and immutable provenance roundtrip.
5. Runtime code changed, so old runtime certificates do not certify this patch. Use the existing A/B Harbor full-fake procedure once against the final merged source, then the existing unified-entry single SQLite fake slot. Do not create another launcher or require a new method registration.
6. Fake integration must use actual displayed source IDs/field bodies, not assumptions that every source ID matches `s[0-9a-f]+`; memory citations now use memory IDs. Include a valid update and invalid sibling, confirm partial success, continued Phase 2, reminder delivery and later silent behavior.
7. Adjust only local paths/import prerequisites and narrowly necessary fixture bindings. Do not relax exact matching, restore batch rollback, change Phase 2, add roles, alter benchmarks or launch real runs.
8. Preserve failed attempts, report pass/fail/skip separately, remove only owned fake authorization/resources, commit necessary evidence, push and read back exact SHA. Stop for main-thread review before a real run.

## Honest limitations

Literal evidence binding still cannot prove an interpretation, prevent omission of counterevidence, ensure a useful reminder, or guarantee Task success. Independent operation commits may produce semantically inconsistent memories; no new semantic reviewer is claimed. Explicit single-record updates protect mechanical replacement integrity, not semantic truth. Public projections are not private raw bytes.
