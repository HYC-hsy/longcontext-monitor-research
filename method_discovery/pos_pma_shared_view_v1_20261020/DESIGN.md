# pos_pma_shared_view_v1 — offline implementation contract

This is a separately selected, default-off research mode. It does not modify the
fixed PoS or PMA vendors, does not authorize a live run, and does not add an
evaluator or completion gate.

For each eligible actor batch, the order is: archive actual action/observation;
run PMA Phase 1 if the existing trigger fires; freeze exactly one rendered bank
selection and its available input-source identities; run one PoS update with that
historical context visible to updater and applicable audit/repair calls; then
run PMA Phase 2 over that same selection and the final adopted PoS state. The
next GA request keeps its ordinary history and receives one temporary auxiliary
view containing the committed state, original frontier-relevant world,
recovery, and optional successfully parsed advice. The GA alone acts or ends.

At initialization, the task-only host input remains task text, not a tool
observation or progress transition. Trigger step 1 is checked once. When it
fires, Phase 1 precedes PoS initialization, and Phase 2 follows it. Terminal
real batches retain the existing PoS terminal update and skip both PMA phases;
finish alone creates no transition. MAX_TURNS retains the host's actual done
flag rather than synthesizing one.

The frozen bank selection consists of rendered text, ordered category/ID,
content hash, bank version, and available source event identity. Source
mapping means the event was visible when an entry was created, never that it
supports the entry's claims. Missing legacy provenance is unknown. Historical
sources are not replayed as new PoS transitions. Audit citation eligibility is
derived only from actual visible permitted tool-result segments, after the
original audit projection and deduplication by identity, field, hash and span.
The task-only initial row, memory prose, advice, next_prompt and actor analysis
cannot become tool evidence.

The new mode removes only the earlier complement adapter's 16K/12K character
caps, four-source/two-thousand-character/eight-record selection caps, 2120
wrapper guard, 90KB request cap and candidate-only pretrim. It retains native
PMA render thresholds and BM25 settings, PoS local audit projection, GA history
policy, fixed task deadline, strict capture, typed failures and Task complete-
response behavior. Character counts, UTF-8 bytes and tokens are distinct;
provider hard context limit remains unknown unless established by configuration.

Receipt stages are prepared, transport-observed and request-accepted. Only an
accepted Task response binds advice for possible next-transition review; this
does not prove the model understood the advice. Unknown send status stays
unknown. Fatal auxiliary or capture failure stops this candidate without
changing already executed tools, the Task's factual terminal state, or an
independent native evaluation observation.

All offline fixtures must force finite fake transport at the final network
boundary. `execution_authorized` is false. No live compatibility probe or
formal task is in scope.
