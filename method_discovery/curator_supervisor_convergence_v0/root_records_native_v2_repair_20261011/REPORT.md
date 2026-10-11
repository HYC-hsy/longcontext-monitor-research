# root_records_native_v2 limited repair — zero-model delivery

Code baseline: `65f7058a143a997f33471d76800af1d3add28630`.
Archive baseline: `3c50e34cae5b01c9859928ef068f22196b6f2ee6`.
Repair code commit: `db36f67e75ad9c10f7bcb124ad060a6505e6bcf5`.
The archived baseline and Kitex forensic results were not modified.

## Exact changes

- `agent.py`: the bounded second continuation attempt now puts the identical repair text in the temporary history entry and `maintenance_prompt`, with `request_purpose=format_repair`. The original system, purpose, maintenance prompt, transaction marker, and history tail are restored in `finally`; rejected response blocks are not appended or executed. The existing pre-send suffix validator remains strict.
- `agent.py`: each committed v2 root, including `applied=false`, creates the same handoff/source/projected pending verification record. The manifest still truthfully reports `applied=false`; off and v1 retain their prior condition. No RER rule changed.
- `test_root_records_native_v2.py`: fake SSE through the real `_prepare_continuation` and pre-send hook exercises both unverified and verified roots, bounded format repair, cleanup, and a tampered prompt rejected before a second transport. Empty and already-native histories exercise no-op commit, valid capture, wrong handoff, tampered archive, and a recorded/verified native tool-payload archival transform. Historical tool calls are not executed.

## Source identity correction

The prior `AUDIT_PACKAGE.txt` enumerated SHA-256 from `Path.read_bytes()` on the Windows working tree, not bytes from the cited Git commit. Its `agent.py` claim was `68777d578a3081f14f716f0be6f5887f2e527dd2aa0d77cb664ea76ddf01136b`; its `runtime.py` claim was `8c124dc37c0d64de5e4040a095c8aa16ebefec3e422ecc02d2ae4155d0557642`. The old Git blob byte SHA-256 values are `34d2feff37c2931744bf9e8c19ee44160dfa66bba2537a971266881f872ef507` and `1ff1e28202661873d77fede233f8b0c94ff032cfb7513f83453290727b4f5b9e`, respectively. The old audit wording was wrong; those worktree hashes were not commit-byte identities. The attached identity table independently computes `git cat-file blob COMMIT:path`, Git object IDs, current `Path.read_bytes()` hashes, byte sizes, and whether CRLF-to-LF normalization makes current workspace bytes equal the committed blob. `core.autocrlf=true`; current `runtime.py` and repaired `agent.py` normalize exactly to their respective committed blobs. The old pre-repair `agent.py` working-tree bytes themselves were not separately retained, so their exact byte-level difference cannot be reconstructed solely from its old SHA; no semantic difference is inferred from the hash mismatch.

## Test and validity limits

The attached package records the exact zero-model command, exit code, complete stdout/stderr, and full code diff. The targeted suite covers provider/projection/CRS/RHR/RER/root ceiling and continuation seams. Two pre-existing tests are explicitly excluded: `test_frozen_prompt_and_provider` asserts an obsolete provider-byte identity from `29bdcb...`, and `test_forced_compaction_then_replaced_root_uses_current_contract` cannot import `shortuuid` in this host Python. Neither is counted as passed. The Windows pytest atexit warning about an unrelated old temporary directory is included verbatim; pytest's actual exit status is recorded.

No real Task, Supervisor, provider API, native evaluator, training, or scoring-model calls were made. Pilot profile selection remains `root_records_v1`; v2 remains opt-in and default-off. Real endpoint acceptance of native historical tool messages after signed thinking removal remains unverified. This repair makes no claim about live Kitex outcomes, cognition, or scientific effect.
