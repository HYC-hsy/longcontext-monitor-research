# P2 input-only cleanup (offline engineering validation)

Production base: `e80648be9f40a44fd4045d75b2ad18b286208fdf`.
The changed selector and context hook, plus unchanged tag contract, were fetched
at that exact ref. `GenericAgent-main/ga.py` was also inspected at that ref:
`_get_anchor_prompt` produces the known next-prompt wrapper; `agent_loop` passes
that next prompt as `observation/content`, separately from `tool_results`.

## Boundary

- Same upstream task and last-eight-step window, no new retrieval/model/state
  summarization. The P1 raw observation, source blocks, evidence/quotes, author
  catalog, accepted events and original archives are unchanged.
- P2 catalogue comes first and replaces duplicate bank/gap views. Full TASK and
  each eligible committed memory appear once there, in the existing alias order.
  Original binding status/disposition/reason are retained as short annotations;
  derived memory/source-alignment-not-proof remains explicit. Repeated binding
  quotes/excerpts are not reprinted. Status is internal and not selectable.
- Only the known GA `observation/content` wrapper is projected. An anchored
  grammar removes its working-memory/history portion, not arbitrary matching
  strings elsewhere. Current turn and subsequent host instructions are retained.
  Latest known key_info and earlier_context are each retained once, labelled non-selectable, at its source
  step; it may contain unique older information. Ambiguous/nested or unknown
  wrappers stay literal and get a hash in `retained_unknown`.
- Every command (including more than five), public response, tool-result string,
  call ID, stdout/stderr/timeout/exit metadata, ordering and accepted event identity
  survives. Tool results are opaque: no recursive decoding, truncation or tag
  deletion. JSON presentation escaping changes, not field values; visible JSON uses Unicode
  directly rather than ASCII escapes.
- Snapshot, alias/revision binding, output parsing and delivery-time validation
  are unchanged. Missing prepared provenance falls back to the complete original
  observation rather than guessing. `selection_context` is a host-side dependency,
  not a reason to expand GA-container imports.

## Local real replay / public synthetic tests

`replay_saved.py PATH/visible/memory_payload.jsonl` reads only public selection
payloads; it never accesses research_events or hidden reasoning. It inverts the
known saved formatter for this archived replay (not a production input parser).
The real cycle-14 fixture and all real trajectory text remain local only and are
not included in this repository. `replay_results.json` contains the 18-run hashes,
counts and removal manifests, not task/command/output bodies. The replay script
accepts user-supplied local material and prints statistics; it does not write a
trajectory fixture into the repository. The default long-window regression builds
fresh synthetic animation data, with no copied real-task content. It covers the
same wrapper structure, long literal-tag stdout, tool identities, timeout,
TASK/M aliases, and one-copy earlier_context/key_info retention.

For those public saved prompts: total **522,809 -> 325,670 characters**; original
peak cycle 14 **51,363 -> 32,960**. These are characters, not tokens. Replay
reconstructed entries do not contain accepted-event identity metadata absent from
the saved formatted input; production preserves that metadata when supplied, so
these are exact replay-render lengths, not a forecast of live request bytes.
All original eight steps, their command strings, public responses and complete
nested tool_results are equality-asserted, not merely checked for shorter text.
No model inference, Task, eval, experiment or old-run mutation occurred.

Run:

```
python -m unittest pma_evidence_review.tests.test_selection_context pma_evidence_review.tests.test_runtime_boundary pma_evidence_review.tests.test_ga_spool_import_boundary -v
```

16 checks passed (`checks.log`): production prepare/render wiring and unchanged
window, opaque long tagged stdout, seven tools/complex JSON/timeout, unknown and
ambiguous wrapper retention, empty history, catalogue ordering, exact task and
memory, stale-revision rejection, original no-intervention/intervene protocol, Unicode/newline fidelity and latest
available earlier_context preservation when a newer anchor lacks that block,
synthetic long-window preservation, runtime report/persistence and isolated GA import boundary.
The runtime harness uses documented optional-dependency import doubles, not real
providers. These checks establish engineering preservation only, not improved
memory selection, reduced harmful silence, task quality, attention or cost.
