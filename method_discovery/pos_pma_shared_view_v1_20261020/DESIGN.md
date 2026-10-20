# pos_pma_shared_view_v1 - offline implementation contract

This is a separately selected, default-off research mode. It does not modify
the fixed PoS or PMA vendors, authorize a live run, or add a completion gate.

At each eligible actor batch the order is: archive actual action/observation;
run PMA Phase 1 if its existing trigger fires; freeze exactly one rendered bank
selection and available input-source identities; run one PoS update with that
history visible to updater and applicable audit/repair calls; then run PMA
Phase 2 over the same selection and final adopted PoS state. The next GA
request keeps ordinary history and receives one temporary view with committed
state, upstream frontier-relevant world, recovery and optional parsed advice.
The GA alone acts or ends.

Initialization keeps the host's duplicated task text as task-only content,
never as a tool observation or progress transition. Trigger step 1 is checked
once. When it fires, Phase 1 precedes PoS initialization and Phase 2 follows.
Terminal real batches keep the existing PoS terminal update but skip PMA;
finish alone makes no transition. MAX_TURNS uses the host's actual done flag.

The frozen bank selection records rendered text, ordered category/ID, content
hash, bank version and available source-event identity. An input-source map
means that material was visible when an entry was created, not that it supports
the entry's claims. Missing legacy provenance is unknown. History is not
replayed as new PoS transitions. Audit citations derive only from actually
visible tool-result segments under the original projection, deduplicated by
identity, field, hash and span. Task-only initial text, memory prose, advice,
next_prompt and actor analysis are not tool evidence.

Repair at `52f85a34`: updater and applicable repair use the frozen selection
plus its available original sources; initial audit and re-audit additionally
receive the *same frozen rendered memory body* in a separately labelled,
non-citable history message. The latter is not another tool-result projection.
The selected input-source union is prepared before Phase 2 and appears in its
actual advisory request, including sources already outside PMA's recent window.
Missing or shortened source data remains marked as such, never reconstructed.

The Sentinel compacts each real PoS step only once. Within a step it keys
receipts by event ID and field, so two distinct tool results remain distinct,
while current-window, selected-history and prior-advice copies of the same
receipt cannot each consume a new 6000-character allowance. Projection logs
record field paths, segment hashes, offsets and omitted spans. The validator
sees only those separately displayed tool pieces; neither memory prose nor
unshown middle bytes gain citation eligibility. Plain observations without an
identified tool-result envelope do not become tool citations in this mode.

Every reset/update has a separate current-attempt stage. A real transition is
recorded once before auxiliary work. A Phase 1 failure can leave committed
PMA CRUD and provenance, but leaves PoS/Phase 2 as not attempted and the new
transition unreviewed. Prior adopted PoS state, bank, and delivered-advice
history remain available without masquerading as this attempt's outputs.

| Boundary | Source and effective value | New-mode treatment |
| --- | --- | --- |
| PMA wake/window | Frozen trigger: interval 1, first step true, eight recent actor steps in the synthetic run | One decision-batch trigger, not one per tool; existing configuration remains authoritative. |
| PMA bank selection | Fixed PMA constructor: max_memory_in_prompt=50, use_bm25_prefilter=true; existing adapter uses top 20 per bank only above that threshold | One render is frozen and reused in Phase 2; no new retriever or source-count cap. |
| PoS audit observation | Fixed `beliefSentinel.py` default audit_observation_max_chars=6000 | Historical citable tool fields use this projection; updater/Phase 2 do not inherit it. |
| PoS health/progress | Fixed released configuration, including K=8 and health threshold 0.25 | Original update/scoring/recovery mathematics and unscored state remain. |
| Old complement caps | Former 16K panel/advisory, 12K revision, four history events, 2000 characters/event, eight related records, 2120 wrapper and 90KB request checks | Removed only in the new mode; old complement keeps them. |
| Task/role transport | Frozen profile and fixed Task deadline; strict capture and Task complete-response policy unchanged | No replacement context/token limit is invented. Provider hard context limit is unknown. |

Character counts, serialized UTF-8 bytes and tokens are distinct. Prompt size
is not proof of final HTTP payload size or provider context acceptance. Explicit
provider limit failures, capture faults, deadline and cancellation retain their
existing failure handling; no hidden content deletion/retry is added.

Receipt stages are prepared, transport-observed and request-accepted. Only an
accepted Task response binds advice for possible next-transition review; this
does not prove model understanding. Unknown send status stays unknown. Fatal
auxiliary or capture failure stops this candidate without changing already
executed tools, factual Task terminal state or independent evaluation record.

All offline fixtures force finite fake transport at the last model boundary.
`execution_authorized` is false. A live probe or formal task is out of scope.
