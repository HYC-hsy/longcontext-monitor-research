# Split protocol v2: actual reuse and limits

Base: 6d2304ddea84a489ad0c0c9fcbad9a3cbdc8ca88. New strategy: claim-split-same-evidence-v2.
Direct remains semantic-support-one-sentence-v1, with unchanged prompt construction and stop behavior.

Inspected fixed sources (all MIT):
- eea/rag-facts-check b78a08213ba7e6d9e587bfa3134ba9047cfaf677: checker.py ClaimExtractor._to_claim_objects,
  ClaimVerifier._single_batch_verify; spans.py merge_overlapping_spans/find_span_in_text;
  prompts/claim-extraction-system.txt; tests/test_spans.py; LICENSE.md.
- aberaio/sourcecheck d81493d239ea084c6063695b6e762c2626dd5646: verifier.py verify_claim,
  _resolve_and_fetch, verify; extract.py _sentences/CitationExtractor; abstention.py; LICENSE.
- shmsw25/FActScore f28272deffcf33efc1f1117d5479c10bb75221a9: atomic_facts.py
  get_atomic_facts_from_paragraph/get_init_atomic_facts_from_sentence/postprocess_atomic_facts,
  factscorer.py _get_score; LICENSE.

Actual new copied code: spans.py merge_overlapping_spans, unchanged body, in vendor/rag_span_union.py.
RAG_LICENSE retained. It runs only on already validated exact spans, max_gap=0. It does not merge
or deduplicate Claim objects. Existing vendored Claim/Span/VerificationResult and batch/document
formatters continue executing. Existing strict json_value, closed citation preparation, transport,
atomic draft publication, original-author one-repair, and receipts are reused.

New host adaptations, not upstream implementations:
- Unique exact original_text determines coordinates; supplied integer offsets are advisory only
  in this unambiguous case, with corrections recorded. Repeated original_text still requires exact
  valid paired offsets. No case/space/punctuation normalization, fuzzy repair or first-match fallback.
- Union complement records every omitted character verbatim, including whitespace, punctuation,
  operators, negation, chronology and completion. No connector whitelist. Diagnostics and full A
  enter the single batch. Structural gaps do not establish semantic failure or success. All claims
  must pass AND batch decomposition_complete must be true. That model judgment can still be wrong.
- Batch v2 asks only results (ID/verdict/E IDs/explanation), Boolean decomposition_complete and
  coverage_explanation. True may have empty explanation; false requires nonempty explanation.
  Host feedback anchors default to validated claim.original_text or full immutable A. Optional old
  fragment echoes are accepted for historical replay: use only exact valid substrings; otherwise
  fall back to host anchors without changing the verdict. Raw output remains recorded.
- Only split parser failures are operation-local. They may use the existing one-author-repair slot;
  feedback explicitly says technical failure/no semantic verdict. Failed explicit targets are blocked
  for the rest of the cycle, including status. Independent targets continue, with no rollback of prior
  commits. Transport/protocol/truncation/cancellation/stale-base/host failures still stop globally.
  Sourcecheck Verifier.verify does NOT implement this isolation; this is a new host adaptation.

Not reused: upstream factual-only exclusions, same-span deduplication, missing-ID semantic defaults,
normalizing/fuzzy span search, automatic re-extraction, NLI thresholds, retrieval, FActScore demos,
biography postprocessing, binary parsing or mean aggregation. No additional model role or call phase.
Successful attempt remains exactly split + one whole claim-list batch; repaired operation starts both anew.

Certificates: v2 has new strategy/request identities and changed source hashes, including copied span helper.
validate_attempt still reconstructs exact current requests, parser results and aggregate. Old v1/direct
certificates cannot certify v2; keep historical checkout/certificates for historical replay only.
