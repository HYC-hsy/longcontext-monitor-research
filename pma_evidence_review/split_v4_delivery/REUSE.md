# Pinned upstream comparison for opt-in v4

The three upstream repositories were inspected at the exact commits below. Existing
vendored RAG formatter/result container and MIT notices remain unchanged in
`pma_evidence_review/vendor/`; this change does not transplant a new dependency.

| Upstream file / function or prompt | Local position | Reuse status and adaptation | Why / focused check |
| --- | --- | --- | --- |
| [EEA `checker.py` `ClaimExtractor._extract_chunk`, `extract`](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/rag_facts_check/checker.py#L144-L229), extraction prompt invoked by `_extract_chunk` | `claim_split_semantic.py:split_request`, retained `claim_split_simple.py:split_stage` | Adapt call/parse sequence; no answer chunking, coordinate repair, old client, or extra refinement call | Operation A is already the atomic host unit. Split payload excludes B; `test_split_payload_has_no_evidence_and_batch_reuses_frozen_b`. |
| [EEA `checker.py` `ClaimVerifier` batch and result alignment](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/rag_facts_check/checker.py#L684-L755), pinned verification prompts | `claim_split_simple.py:verification_request`, `parse_batch`, `claim_split_semantic.py:VERIFY_SYSTEM` | Direct reuse of existing MIT `vendor/rag_prompts.py:format_documents` and `vendor/rag_models.py:VerificationResult`; adapt target to complete original operation plus ordered claims, one frozen B | No per-claim model call or retrieval; exact cardinality and whole-op judgment tested by `test_partial_and_bad_cardinality_do_not_publish_semantic_success`. |
| [FActScore `atomic_facts.py` `AtomicFactGenerator.get_init_atomic_facts_from_sentence`](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/atomic_facts.py#L85-L129) | `claim_split_semantic.py:SPLIT_SYSTEM` | Adapt input-to-output demonstration *organization*, with four newly written generic examples. No FActScore code, biography demos, BM25, spaCy, or client copied | The original examples are biography factual atoms; task obligations, conditions and causality require different examples. Test checks prompt boundary and frozen sample separation. |
| [Sourcecheck `tests/test_adversarial.py` negative/positive and argument-direction cases](https://github.com/aberaio/sourcecheck/blob/d81493d239ea084c6063695b6e762c2626dd5646/tests/test_adversarial.py#L17-L77) | `split_v4_delivery/SMALL_SAMPLES.json` derived causal/conditional controls; `claim_split_semantic.py:VERIFY_SYSTEM` | Adapt paired positive/negative *test structure*, not original case text or lexical threshold | A subject/condition reversal must not pass by word overlap. `test_frozen_small_comparison_materials_and_delete_na` verifies source identity/plan separation; semantic effect awaits real A/B. |

All three pinned repositories have MIT notices as recorded in the existing
`pma_evidence_review/REUSE.md` / `claim_split_delivery/REUSE.md`. RAG and
Sourcecheck vendored license copies are retained; no new FActScore or Sourcecheck
code is copied. The new prompt wording and derived controls are original local
adaptations. Sourcecheck's lexical score is deliberately not an entailment gate.
