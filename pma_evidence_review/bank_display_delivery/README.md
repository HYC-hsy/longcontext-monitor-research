# PMA plain bank + display selection

Explicit new candidate: `method=pma-gap`, `memory_maintenance_policy=pma-bank-display-v1`.
Baseline: `e79f57b359124fe061bd603310ba1c45973cf97b`. Old methods and runs remain frozen.
Publication approved and complete: remote source commit `58bc9be3484c55f26b7f31a399a6f1246f1c6560` has exactly the full tree of local `8b73e610a6b942177b25818f6a4b437f5d960ee8`. Its production bytes match tested local `ac4bc56411c443b61300672d5addc7abf6c19b94`. A following delivery-only commit updates these publication records; use the final fixed remote SHA reported with this delivery. Local SHAs describe provenance, not uploaded refs.

The factory creates exactly `GapMemory`; Agent MRO is `BankDisplayAgent -> VerbatimSelectionMixin -> GapMemoryAgent -> MemoryAgent`.
Knowledge/experience saves create IDs from content. Status overwrites. Delete uses ID. Existing save_gap adds the separate GAP view. Public tools equal the pinned four BANK_TOOLS plus existing GAP_TOOL, including descriptions and parameter schemas.
No evidence inputs, same-ID edits, revision/blob/tombstone store, publication queue or reviewer. Extra arguments may be ignored by the original four executors; the public schema does not advertise them. Existing GAP executor rejects extra arguments.
Persistence retains only status, knowledge, procedural and gaps with original entry metadata. Candidate loading rejects extra top-level fields and evidence-store instances; no migration or old-bank conversion is provided. New runs start fresh.

P1 keeps task, bank/status and projected recent eight visible steps. All available commands/results survive; the old first-five-command presentation is not used for this candidate. Retrieval query, candidate order and eight-step window remain unchanged. Existing status truncation remains: over 2000 characters becomes its first 2000 plus `...`. BM25 stays enabled with the original 50-entry threshold and top 20 knowledge/top 20 procedural prefilter; GAP view remains separate.
P2 changes responsibility wording to display useful original text; TASK/M aliases, parser, allowed fences, empty choice and host original-text delivery remain unchanged. Its transient Item.revision is an empty compatibility field, never a stored version. Call/cycle/task binding and full current id/category/content equality are checked at parse and again before delivery. Ordinary operation logs and per-cycle bank snapshots remain.
Old selection defaults retain identical rendered text; tiny hooks permit the new system, ordinary-memory note and omission of absent binding fields. No new ranking, reasons, scores or reminder quota.

The supplied prompts follow completeness, concision and naturalness: retain original save angles and Selective Attention skeleton; describe only actual content-only tools; omit removed binding/version explanations. SYSTEMS.json records actual client-captured systems and the complete unchanged original-plus-GAP schema.
Engineering results: directed 57/57; strict 471/472 with one pre-existing U/A fixture error, no skips or dependency doubles. See TEST_RESULTS.json. Fake clients do not validate selection quality or task benefit.

Known boundaries: operations are independent, not transactional. Save-first is advice, not protection: failed save can be followed by successful delete; successful save can remain after failed delete. Invalid JSON can abort a batch during original pre-parsing; P2 may still run after P1 failure. No new rollback/revision machinery was added. A stale-selection test exposed an unrelated candidate-audit branch; it now checks candidate ownership before reading variant fields.
Upstream reference: `yifannnwu/proactive-memory-agent@89e5c0d6aadfe531a1aee42fd290d48be89973dd`; vendored code unchanged. Prompt wording supplied and reviewed by the parent; no semantic evaluation performed here.
