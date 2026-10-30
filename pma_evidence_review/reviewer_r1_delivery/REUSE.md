# Pinned upstream-to-local reuse map

Existing upstream copies and license notices under `pma_evidence_review/vendor/`
remain unchanged. This candidate copies no new upstream code or sample wording;
the three semantic comparisons are original adaptations for this project.

| Fixed upstream passage | Local position | Reuse and adaptation | Reason / check |
| --- | --- | --- | --- |
| [EEA RAG Facts Check, evidence-first system prompt, lines 3–18](https://github.com/eea/rag-facts-check/blob/b78a08213ba7e6d9e587bfa3134ba9047cfaf677/prompts/claim-verification-evidence-first-system.txt#L3-L18), already retained with MIT notice as `vendor/prompts/claim-verification-evidence-first-system.txt` | `claim_split_semantic.py:VERIFY_SYSTEM`; `claim_split_simple.py:verification_request` | Adapt the read-evidence → compare → verdict sequence. Reuse the already-vendored document formatter, not the upstream per-claim response format or client. | One operation and all frozen claims go in one batch; test compares both model-visible payloads. |
| [FActScore, `atomic_facts.py` lines 114–125](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/atomic_facts.py#L114-L125) and [example assembly lines 99–112](https://github.com/shmsw25/FActScore/blob/f28272deffcf33efc1f1117d5479c10bb75221a9/factscore/atomic_facts.py#L99-L112) | Existing `claim_split_semantic.py:SPLIT_SYSTEM`; candidate reviewer examples in `VERIFY_SYSTEM` | Adapt input/output example organization; no FActScore biography examples, code, BM25, spaCy, or model client copied. | Split prompt is unchanged; reviewer illustrations are distinct from all nine controls. |
| [Sourcecheck, `test_adversarial.py` lines 16–70](https://github.com/aberaio/sourcecheck/blob/d81493d239ea084c6063695b6e762c2626dd5646/tests/test_adversarial.py#L16-L70) | `reviewer_r1_delivery/FROZEN_CASES.json` and `freeze_cases.py:controls` | Adapt paired positive/negative structure, not original strings or lexical score. | Each of the three control groups tests narrower supported, overreach insufficient, and sufficient strong-positive B without changing A after seeing B. |

The existing `pma_evidence_review/REUSE.md` and `vendor/RAG_LICENSE` retain RAG's
license attribution. FActScore and Sourcecheck material is referenced, not copied.
Neither upstream project supplies a complete solution for requirement/completion,
qualified quantifiers, container-specific observations, or gap deletion here.
