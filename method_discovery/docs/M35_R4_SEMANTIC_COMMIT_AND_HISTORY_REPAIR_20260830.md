# M3.5 R4: Semantic Commit and Bounded Continuity Repair

Date: 2026-08-30
Status: engineering-complete; cumulative real-task validation pending

## Triggering real-task evidence

Run `m3-m35_h4_minimal_frontstage-fyn-2.2.0-roadmap-r4` showed that the
monitor could discover concrete contract and test-oracle conflicts, but a correct
intervention was repeatedly delayed or replaced by recovery because the model-authored
full root ledger violated stable runtime identity. Completion-review history then grew
from roughly 70k characters to more than 800k characters. The run was stopped after
203 task turns without a verifier result because monitor cost and latency were abnormal.

This evidence diagnoses a control-delivery and continuity failure, not an absence of
semantic monitoring ability.

## Repair

1. The model may emit sparse `root_obligation_updates` using a short exact quote or an
   unambiguous natural reference. It no longer has to remember stable ids or reproduce
   the complete ledger. The runtime performs only identity binding, unchanged-row
   inheritance, transactional commit, and ambiguity abstention.
2. An ambiguous update never receives a fuzzy guessed identity. It preserves existing
   authority. A justified intervention is still delivered; `allow_complete` remains
   strict and cannot proceed with an ambiguous semantic update.
3. Minimal-frontstage continuity now persists the model's own natural cognitive
   checkpoint. When live history exceeds its bound, exact dialogue is archived and the
   next call receives the working state plus a short recent tail. Large tail messages
   become retrievable receipts. This deterministic fallback does not require another
   model call and remains active during an open repair episode.
4. Turn-0 initialization is followed by one early calibration observation after a
   small real progress window (at most three settled task turns). After that review,
   the same monitor's own `review_after_turns` plan controls patrol cadence. The outer
   runtime does not classify event semantics and task execution remains non-blocking.

## Preserved boundaries

- M1-C and M2-C state/revision mechanisms remain enabled and unchanged in purpose.
- No online checker, verifier, hidden test, or gold answer is introduced.
- Ordinary task execution never waits for patrol review.
- Stable ids, version history, and atomic state commit remain runtime-owned and auditable.
- The monitor retains freedom to inspect, remain silent, intervene, focus, or return to
  patrol; the repair removes bookkeeping burden rather than replacing judgment with rules.

## Engineering evidence

- GenericAgent full suite: `332 passed`.
- Harbor/runner/M3 gate related suite: `77 passed`.
- Added deterministic coverage for id-free natural references, ambiguous-reference
  abstention, intervention preservation, strict completion, bounded open-repair history,
  and one-time initial calibration.

These results establish implementation and regression safety only. They do not establish
task-quality improvement, latency reduction, or cost reduction until a separately approved
complete real-task run is performed.
