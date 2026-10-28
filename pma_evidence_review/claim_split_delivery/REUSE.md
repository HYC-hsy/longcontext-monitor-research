# Same-submitted-evidence claim splitting: reuse and trace provenance

## Scope

This implementation extends baseline `f97033e98e36386474230ccc14f0c19f8a00e7ce`.
For one submitted operation A, it extracts the complete claim list and reviews
all those claims together in **one batch verification call** against one complete
submitted evidence package B. Analysis and commit granularity remain one original
operation; splitting does not create a separate verification call per claim.
One successful audit attempt therefore has a split call followed by one batch
review call, irrespective of the number of claims. It does not retrieve full logs,
expand evidence, add an external checker, or establish actual task completion.
No live claim-split model evaluation was performed while preparing this record.

## Pinned source inspection and licenses

The actual source files, not only README descriptions, were inspected locally.
`PROVENANCE.json` records verified source-file hashes, including each license.

| Repository | Exact commit | License |
| --- | --- | --- |
| [eea/rag-facts-check](https://github.com/eea/rag-facts-check) | `b78a08213ba7e6d9e587bfa3134ba9047cfaf677` | MIT; European Environment Agency, 2026 |
| [aberaio/sourcecheck](https://github.com/aberaio/sourcecheck) | `d81493d239ea084c6063695b6e762c2626dd5646` | MIT; Mikias Abera, 2026 |
| [shmsw25/FActScore](https://github.com/shmsw25/FActScore) | `f28272deffcf33efc1f1117d5479c10bb75221a9` | MIT; Sewon Min, 2023 |

Existing copied RAG and Sourcecheck notices remain in
`pma_evidence_review/vendor/RAG_LICENSE` and `SOURCECHECK_LICENSE`.
No new FActScore code was copied. Its MIT license was inspected, not substituted
for a claim of runtime reuse.

## Actual implementation reuse

The locations below were confirmed against `claim_split.py` and by its implementer.
This is an adaptation of the upstream execution skeleton, not an unmodified
transplant of an entire fact-checking framework.

| Upstream code | Local implementation | What is retained; necessary adaptation |
| --- | --- | --- |
| RAG `models.py`: `Span`, `Claim`, `VerificationResult` | Existing `vendor/rag_models.py`; imported by `claim_split.py` | Retained vendored class bodies are executed. Claim indices/source spans and per-claim result containers are used; confidence is not a commit score. |
| RAG `checker.py:398–416`, `ClaimExtractor._to_claim_objects` | `claim_split.parse_split` | Enumerate original fragments, construct `Span`, construct indexed `Claim`. The host locates a unique exact fragment; optional paired start/end coordinates disambiguate repeated text. Missing ambiguous coordinates fail, without fuzzy/first-match fallback. Schema, duplicate and non-whitespace coverage checks precede acceptance. Distinct claims may share one span. |
| RAG `checker.py:178–190,192–240`, extraction call sequence | `split_request`, `_call`, `parse_split`, `assess` | Retain format/request → model call → parse → claim objects. Host transport replaces upstream `LLM.generate`; no upstream automatic refinement, demos or retrieval. |
| RAG `checker.py:790–846`, `ClaimVerifier._single_batch_verify` | `verification_request`, `_call`, `parse_batch`, `assess` | Retain indexed claim-list → one model call → parse → original-input-order result reconstruction. One shared B is displayed for the whole list. Duplicate, unknown and missing indices fail before dict mapping; strict verdict/E-ID validation replaces permissive upstream parsing and default missing-result semantic labels. |
| RAG `prompts.py:163–191`, `format_claim_verification_batch_prompt`, and `:199–250`, `format_documents` | Existing `vendor/rag_prompts.format_claim_verification_batch_prompt`, directly called by `verification_request`; it calls the retained `format_documents` | Both actual reused formatters execute. Indexed claim lines and source-document formatting are retained. Complete JSON-serialized B items use the supported title/text interface with E IDs; full-corpus budgets prevent truncation. The adapter requires the exact generic system prefix/array-output suffix and removes them, supplying one compatible closed E-ID batch contract rather than appending a competing schema. |
| RAG extraction and evidence-first prompt clauses | `SPLIT_SYSTEM`, `VERIFY_SYSTEM` | Adapt independent-assertion splitting, complete statements, original fragments and evidence-before-verdict order. These are new closed contracts, not unchanged upstream prompts: preserve requirements/questions/time/conditions/completion, prohibit evidence additions, and return a single global decomposition-preservation judgment alongside all indexed claim results. |
| Existing local strict parser and closed-evidence contract | `review.json_value`, `citation_review.SYSTEM`, `prompt_strategy.SUPPORT_SENTENCE` | Reuse the f970 duplicate-key-rejecting JSON envelope, closed-source discipline and semantic support sentence. No permissive parser fallback is introduced. |

The new route does **not** instantiate the upstream verifier or call legacy local
`review.parse_results`. Its `parse_batch` adapts upstream indexed reconstruction
and the existing local strict-ID approach to one batch response object containing
all claim rows plus one global coverage judgment. It executes the existing vendored
batch formatter; this is stronger than merely referring to batch verification as
an inspiration. It does not use upstream `verify_batch` chunking or split one
operation's claims across multiple verification calls.

## Sourcecheck and FActScore: inspected, not transplanted

- Sourcecheck `src/sourcecheck/verifier.py`, `Verifier.verify_claim` and
  `_resolve_and_fetch`: source identity must be resolved before grounding. The
  existing local `citation_inputs.prepare` boundary is retained; no remote
  resolver/store/network or scholarly lookup is added.
- Sourcecheck `src/sourcecheck/gating.py:17–26`, `matches_condition` with
  `unsupported`: anything other than a positive supported verdict fails.
  `claim_split.aggregate` applies that strict contract plus nonempty/exact ordered
  cardinality and coverage checks. The Sourcecheck function itself is not copied
  or called. Existing vendored enums remain in the repository; indirect import is
  not claimed as reuse of Sourcecheck's grounding mechanism.
- Sourcecheck `abstention.py`, `PrecisionFirstPolicy.decide`: inspected the
  unresolved/no-content/no-grounding paths. Its scientific-source checks and NLI
  thresholds are not applicable and are not imported.
- FActScore `factscore/atomic_facts.py`, `AtomicFactGenerator.run`,
  `get_atomic_facts_from_paragraph`, `get_init_atomic_facts_from_sentence`, and
  `postprocess_atomic_facts`: inspected sentence→atom extraction and its biography
  filtering. No demos, NLP downloads, biography rules or old provider client are
  imported.
- FActScore `factscore/factscorer.py:209–261`, `FactScorer._get_score`: inspected
  atom-as-input versus passages-as-evidence separation. Its per-atom retrieval,
  permissive binary parsing and mean-supported scoring are not reused.

## Deliberately rejected behaviors

1. RAG's generic extraction prompt excludes questions and hypothetical statements;
   here those must retain their original force instead of disappearing.
2. RAG `ClaimExtractor.extract` deduplicates equal spans (`checker.py:242–267`).
   This can erase different assertions from one compound sentence.
3. RAG `RAGFactsChecker.check` can slice claims to `max_claims`; this implementation
   must block incomplete output rather than silently omit later commitments.
4. RAG `_parse_batch_response` uses substring verdict matching, so `UNSUPPORTED`
   matches `SUPPORTED`, and duplicate indices can overwrite results. Exact local
   schemas/enums are retained instead.
5. RAG `_aggregate` calls supported/total “completeness.” That is a support ratio,
   not proof that all original propositions were extracted.
6. Sourcecheck `CitationExtractor.extract` skips uncited sentences. It cannot
   provide complete operation extraction.
7. FActScore biography postprocessing may remove/replace atoms; entity coverage
   is not proposition coverage. Its permissive fallback can classify malformed
   answers as supported, and its mean score is not an all-required commit gate.
8. Legacy local extraction verifies only fact/deletion kinds. The new path has no
   kind-based exemption or model-selected kind taxonomy.

Structural span coverage does not prove semantic completeness. The one batch review
also sees full A and the complete split list and returns a global
decomposition-preservation judgment. The host requires that judgment and every
indexed claim verdict to pass.
These semantic judgments remain fallible model outputs, not formal guarantees.
The existing one-repair limit remains; a replacement is fully split/reviewed again.
The unchanged delete protocol still cannot use an old write's citations to justify
deletion and is not broadened by this feature.

## Reviewable historical regression inputs

`TRACE_FIXTURES.json` contains two exact materials from the sanitized SQLite
gate-one-repair archive: calls **19** and **61**. Only each fixture's `material`
object is a model-input candidate. Reference expectations and historical raw model
responses are separated and must never be appended to evidence or target context.

- Call 19: the historical whole-operation model said `supported`. Its only quote
  reports no working compiler found after trying cc/gcc; A additionally asserts
  exact command/directory, absent compiler installation and source readiness.
  The reference expectation is `insufficient`, specifically preserving these
  additional commitments rather than calling source readiness mere framing.
- Call 61: the historical model said `contradicted` because setup appears later
  than timeout. The reference expectation is `insufficient`: later setup does not
  itself contradict an earlier historical timeout, while generalization and the
  asserted solution exceed the displayed evidence. This is a design-review label,
  not a newly observed claim-split result or a native verifier verdict.

`PROVENANCE.json` records archive code SHA `f97033e98e36386474230ccc14f0c19f8a00e7ce`
and recorded execution head `7c2260eb1f8898e4f073c1aecb6ad831d10740e1`, source
file/line mappings, verified compressed/decompressed/selected-line hashes,
material/content/B hashes, and upstream source hashes. Original private stream
hashes are explicitly exporter attestations: only available sanitized bytes were
verified here. No full history, neighboring observation, secrets, profiles,
authorization originals or hidden tests are included in the fixtures.

Preparation checks passed: both fixture materials equal their selected archived
request JSON exactly; both historical responses equal their archived response
strings exactly; four selected-line hashes and the fixture-file hash match.
Selected contents were reviewed and a narrow credential-pattern scan found no
matches. This is fixture/provenance validation, not semantic model evaluation.
