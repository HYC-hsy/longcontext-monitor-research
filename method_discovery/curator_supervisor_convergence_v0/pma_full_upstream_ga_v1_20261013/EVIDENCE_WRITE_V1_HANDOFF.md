# PMA-gap evidence write v1 implementation and handoff

## Status and scope

Implemented as optional method **pma-gap-evidence**, research candidate **pma_gap_evidence_v1**. Baseline **pma-gap / pma_gap_memory_v0** remains available and unchanged in its agent/store/prompt source. This is source-provenance engineering, not proof that memory claims are true or task performance improves.

Code source commit delivered on GitHub: **2ab84f82e485e8efb9c63323a4a375a200d67c54**. Its Git tree is **9a966cc5a4f2872befce572d6f54093e3324964c**, identical to the locally tested source tree. Delivery branch: **research/pma-gap-evidence-write-v1-20261024**, forked from **5af52e8af831653f3ac222eb414abf1724ba3f7b**. Later documentation/archive commits do not change runtime source.

No real provider generation, real Task, native task test, official scoring, or Docker/Harbor full-chain certification was performed in this implementation round. Existing scores and archives are untouched. Do not reuse an old candidate certificate or treat these tests as authorization to run a real episode.

## What changed

- Same five tools and original two ordered memory phases. The four content writers accept `content` plus `evidence: [{source, quote}]`. `memory_delete(memory_id)` is unchanged.
- The gap tool is included. Requirement-derived information/achievement gaps and inferred test-quality gaps are allowed; they need visible source anchors, not an observed failing test or a literal copy of the memory body.
- The program labels actual public input blocks, binds exact nonempty unique quotations, derives roles/identities/Unicode positions/hashes, and keeps original text separate from model-authored memory. No fuzzy fallback, guessed source, or default-all source association.
- Phase 1 retains memory categories, selected/total counts, and chronology. Source labels do not become the BM25 query. Phase 2 content rendering, prompt, parser, full gap view, and reminder injection remain inherited.
- A tool-response batch is parsed and bound before mutation, then applied to a detached active-state draft. The shared bank object is published once only after validation. Invalid replacement cannot delete the old gap first. Failure preserves the old active memory and continues Phase 2; there is no reviewer or repair model call.
- Historical source text is shared and retained only when cited or required by ancestry. Reference-only request manifests are stored, not a duplicate full input snapshot per cycle. Old memory references remain `memory_derived`, not fresh observations. Deleted revisions remain traceable.
- `rpds.HashTrieMap` provides mature immutable storage sharing. No hand-built persistent map. Runtime validation covers new deltas and active state; full historical validation is reserved for loading/final saving. Source bodies are not deep-copied or rehashed on each update.
- Final persistence remains at the existing task-end save boundary, with a single bank/provenance checkpoint using temp-file + fsync + replace. This does not provide mid-episode crash recovery.

## Files and reuse

- `gap_evidence.py`: source registration, immutable snapshots, exact binding and receipt validation. Adapted from existing `source_memory.py` and `source_memory_v2.py`; role/offset/version filling is removed from model responsibility.
- `evidence_gap_store.py`: opt-in `EvidenceGapMemory`, staging, same-object publication, revision ancestry, final serialization. Reuses original PMA writers and existing atomic save; uses `rpds-py` rather than copying histories.
- `evidence_gap_agent.py`: opt-in `EvidenceGapMemoryAgent`, role-local schemas/prompt, visible P1 projection, whole-batch preflight. Inherits PMA process and P2.
- `evidence_gap_context.py`: actual GA public event/field projection. Auxiliary `analysis`/`plan` fields and provider hidden reasoning are not registered. Tool-call identity is retained; command-result relationships are not guessed by position.
- `episode.py`: explicit optional construction, context preparation, compact cycle diagnostics. The baseline classes are not given provenance methods, avoiding accidental `hasattr` activation.
- Existing runner/launcher/bridge/worker/certification routing recognizes the optional candidate. New source identity covers the evidence modules, reused provenance source, and dependency declaration. Original short-reuse certificates are rejected for this variant.

OpenWiki inspired prevalidate-before-publish ordering; Graphiti supplied the short-selector/host-identity pattern; LangExtract supplied alignment/Unicode/repetition counterexamples. Their full frameworks are not dependencies. The actual source binder is adapted from existing project code, not falsely described as direct LangExtract import. `rpds-py` is MIT licensed; its package retains its own license.

## Local verification

Python **3.12.14** was available locally. User-side Python 3.13 has not been run here. PMA host tests load the pinned PMA/Harbor source, not a replacement fake bank implementation.

- Core evidence + original gap + actual host object fake-response tests and unified-entry regression: **204 tests passed, 135 subtests passed**.
- Affected GA bridge, capture, original PMA parity and completion-response tests: **42 tests passed, 38 subtests passed**.
- Unchanged evaluator-preparation unit tests in an isolated official Harbor 0.24.0 environment: **16 tests passed**, including all 8 verifier-boundary cases. These mock the environment and do not run task tests.
- Separate source identity check verified **48 committed runtime files**. Counts from overlapping audit reruns are not added to these suites.
- Five new gap-view scenarios exercise requirement-only gaps, test-quality inference from actual visible test code, gap revise/delete + procedural retention, invalid replacement preservation, and complete gap visibility when ordinary BM25 is filtered.
- Independent adversarial audit found and drove fixes for historical validation growth, cyclic ancestry loading, malformed manifest/receipt acceptance, false rollback reporting after publication, and duplicate-source manifest rejection. Final reproductions reject invalid records and accept valid repeated blocks.
- A synthetic retire/replace microbenchmark measured roughly 0.020 s for 100 cycles and 0.103 s for 500 cycles after the storage fix. This excludes LLM calls and is not task latency evidence. Deterministic tests additionally assert hash work does not scale with retained history in the tested fixed-active-size case.

Early broad tests loaded the pinned PMA Harbor 0.1.42 for native verifier tests, which lack the needed native API. The unchanged tests passed in a separate Harbor 0.24.0 process; no vendor/test assertions were weakened. Missing external parity fixtures were fetched from the pinned upstream commit. Package/import setup failures are not method failures or live requests.

## Developer uptake

1. Fetch this branch and merge fast-forward only if the local development branch has not diverged. Do not reset or force-push another thread's work. Otherwise inspect the focused commits before merging.
2. Use the local project Python environment. Install the small optional dependency with that interpreter:
   `python -m pip install -r method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/evidence_requirements.txt`
   Existing PMA dependencies are still required. Do not globally replace Harbor to satisfy the method tests.
3. In a fresh test process, prepend the stage directory, pinned PMA `src`, pinned `external/harbor/src`, repository root, and `experiment_runner` to PYTHONPATH. Set `LITELLM_LOCAL_MODEL_COST_MAP=True` for offline tests to avoid a pricing-map network fetch.
4. Run the new `test_gap_evidence_*.py`, old gap tests, and runner regression. Verify bank identity, two-phase order, normal reminder/silent behavior, and the final bank can be loaded with evidence intact.
5. The existing unified configuration can select `method: pma-gap-evidence`. Keep the previous task/model/evaluation/runtime settings otherwise unchanged; remove any old `runtime_reuse` certificate configuration. The entry is registered, but a fresh exact-source Harbor fake certification still needs the developer's working Docker environment before proposing a real run.
6. Do not launch models, Tasks, or scoring solely because this implementation is merged. This round authorized local implementation/testing/publication only. Any public export of later real provenance must use a reviewed redaction projection, not dump the full bank blindly.

## Deliberate limits

Exact quote binding does not prove entailment, source reliability, missing-test coverage, current validity, or task completion. It does not prevent a wrong interpretation of a genuine receipt. A valid update in the same batch as an invalid one is deferred. P2 deliberately does not yet consume the evidence. Current status truncation is preserved and both proposal and stored-content hashes are recorded. Old legacy entries remain unbound until legitimately revised; no source is fabricated. Original private transport logging is not globally rewritten; newly registered evidence uses only explicit public fields, not a universal secret detector. Disk storage still grows with genuinely retained sources/history.
