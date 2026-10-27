# Reuse ledger for the online gate prototype

This supplements the existing pma_evidence_review/REUSE.md; prior license/attribution files remain intact.
No POS vendor files or upstream model/client settings were modified.

- PMA pinned 89e5c0d: MemoryAgent.process remains the actual maintenance→sync dispatch→selection
  implementation. The gate subclass awaits audit inside its phase1 call, then returns a one-use
  operation cache to the original sync dispatch. MemoryOperation and result objects are reused.
- Repository LatestEvidenceGapMemoryAgent._apply_operation / EvidenceGapMemoryAgent._operation_draft:
  actual inherited calls, not reimplemented alignment. Draft store prepare_publication/publish
  owner-generation validation is called after await, with the same owner object throughout.
- citation_inputs.prepare/candidate: actual calls enforce exact unique submitted quotes, visible
  span hashes and source/revision identity. live_citations constructs a real live envelope rather
  than pretending to load a public archive. citation_review.projection/parse and request formatter
  are reused. Source registry/catalog never contains receipts, reviewer or repair responses.
- prompt_strategy.apply_strategy: extracted unchanged from benchmark.experiment.plan; same exact A,
  historical long-B and one-sentence plans. Online uses the one-sentence strategy; no benchmark
  module/data/reference-label dependency in live code.
- CapturedTransport is the existing text-only client adapter and raw-response capture. Calls still
  use llm.call(prompt, system, tools=None); transport exceptions and illegal tool responses remain
  engineering errors. Repair is one additional author opportunity, not a new model role.
- POS manager._validate_candidate (vendor/belief/manager.py:411–538): architectural inspiration for
  uncommitted candidates, original-author repair, second audit and base retention. Not imported or
  copied: its whole-belief patch format, full-trajectory audit input or pending issue mechanism.
- Current POS strict contract: pos_pma_complement_v1_20261019/shared_view.py:185–196 enables strict;
  vendor/belief/beliefSentinel.py:269–273 distinguishes clean/issues/unusable. The gate likewise
  never treats filtered/invalid/failed results as supported; it uses the citation parser instead.
- Existing RAG b78a082, Sourcecheck d81493 and FActScore f28272 analysis/attribution remain as
  documented in the original reviewer. This gate adds no retrieval/NLI/atomizer code and does not
  claim that any upstream project supplied the new PMA repair or receipt implementation.

New adaptation: per-operation attempt orchestration, constrained replace/withdraw repair protocol,
control-only commit receipts, opt-in mode/config identity and offline host-spool tests.
