# Provenance and reuse

## Executed original implementation

PMA repository: https://github.com/yifannnwu/proactive-memory-agent

Pinned revision: `89e5c0d6aadfe531a1aee42fd290d48be89973dd`.

Existing checkout:
`/workspace/shared/pma_prototypes_20261015/integration/upstream/vendor/pma_89e5c0d`.

The four original Python files (`memory_agent.py`, `universal_memory.py`,
`bm25_search.py`, `trigger.py`) and `LICENSE` are hash-checked and staged
byte-for-byte. `results.json` records exact original hashes. No vendor source
was edited. Original CRUD and parsing are used, not approximated.

The reviewed local harness
`/workspace/shared/deep_supervisor_20261017/lab/integration/run_actual_pma.py`
is pinned to SHA-256
`856f00548f4e497eabf27a4783cd18820ace9441110298c7895043304db8f948`.
It is imported solely for `SOURCE`/`PINS`; its main program does not execute.

## Existing authored adapter/harness

`reference_adapter.py` is an unchanged copy of
`/workspace/shared/reference_revision_v0/adapter.py`, SHA-256
`51355b984483648896ea52cc271c230a60022685a1fce008dee8c0681bb6a5ee`.
Reused objects: `FrozenInputs`, exact-type `ScriptedCall`, fake response shape,
canonical serialization/hash helpers, deadline check, ordered-update suffix.
The older goal-only reader and two-phase smoke wrappers are not invoked.

`reference_evidence.py` is an unchanged copy of the older `evidence.py`, SHA-256
`7923666661d4d654132b00cc2b03edde6c6fd646e4a57c0703d36556ad56830a`.
It verifies all 42 archive members and extracts the three exact original task,
observation, and bank-before inputs. Captured model replies are never used as
gold or as runtime helper input.

The new runner adapts the existing `reference_revision_v0/run_fake.py` isolation,
staging, and audit pattern, whose SHA-256 is
`49d64552641cf7ea9f6cb7f2ccfb6b80b6ce571206373fa56c2b5c693312827c`.
The original directory remains unchanged.

## Existing deterministic EB projection

`input_views.py` is the exact 123-line added-file body for
`decision_phase2_views.py`, extracted without edits from the already retained
`input_views54_audit_20261017/integrity/IMPLEMENTATION_DIFF.patch`.

Patch SHA-256: `2ca4dc0057cef6e4693e380ab5ab8a3d6a646f977d01dac13c10acf4260e47aa`.

Extracted implementation SHA-256:
`8b03ecf0232a9310cec18e95909fabde95eb75881fd2be376548df79da6baaee`.

Upstream retained archive:
https://github.com/HYC-hsy/longcontext-monitor-research/blob/52f2b5314c7861eb098ef14126c526bde89a85a4/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/decision_phase2_views.py

The new runner checks reproduced EB output against all six archived exact F/EB
request pairs (43 steps), not merely hashes advertised by an implementation.
The archived launch scripts, provider code, and original experiment tests are
not executed. No code or dependency was newly downloaded for this task.

## Inputs, design, and adaptation

Public source archive:
`/workspace/scratch/ae13762e0e4d/current_evidence/CONSEQUENCE_THREE_CASE_PUBLIC_EVIDENCE.txt`.
SHA-256: `8a9ba2f80fe62e233d06a096693996266763b61df4450dcf6e5c70665d20528c`.

The design contract and independent 54-call audit were read. Their copied
snapshots are recorded in `reuse_manifest.json`; they are not executable code.
The design file changed during development, so it is intentionally snapshotted
rather than forcing the live research document to stay unchanged.

The implemented design uses Phase-1-only readout injection and
a cheap zero-helper replay of the exact source packet. Those are the
new seam choices implemented here. No Phase-2 direct-readout arm was retained. Original PMA retrieval defaults are
unchanged; the exposed reader receives the original selected bank view.

All synthetic semantic responses and expected scenarios are confined to
`checks.py`. The generic production adapter contains no sampler/compressor
answer rules or truth labels. A scripted favorable response establishes only
that the plumbing can carry that response.

## Evidence limits

The archive inputs have historical source/order qualifications; preserving them
does not remove those qualifications. Hashes establish byte identity, not truth,
execution authority, observation completeness, or semantic entailment.

No new license is invented for the local research files. The unchanged PMA
Apache-2.0 license is retained. The original execution did not publish or redistribute files. This publication
copy is part of the dated research archive; it remains dependent on the pinned
shared-filesystem sources described above.
