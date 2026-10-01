# Minimal research checkpoint boundary (discussion only)

Purpose: bind one historical consequential Supervisor state `E_t` to the task world `X_t` before a controlled transition. This is a proposed **research artifact boundary**, not a production design or an authorization to build a replay system.

## Required for an exact selected-boundary experiment

- **Epistemic:** byte-exact `monitor/working.md`; the provider History prefix actually used at that boundary; system/tool/model-config identity; review ID, public cursor and task turn; effective completion proposal and pending-control/delivery identities. Record whether a request or tool was already in flight; select a quiescent boundary when possible.
- **World:** the workspace bytes at the *same* boundary plus a file manifest and original task/image identity. Capture must be coordinated with Task writes or explicitly marked non-atomic/incomplete; otherwise `E_t` and `X_t` can refer to different worlds.
- **Binding:** one checkpoint ID relating those two sides, a public-event prefix/cursor, capture order and their digests. A transition applied later must have an independently recorded before/after event boundary.
- **WTV continuity:** either preserve the previous Supervisor sample/baseline identity, or explicitly establish a new baseline on the restored `X_t` **before** applying the controlled change. Recreated mtime/ctime values cannot silently impersonate the historical WTV fingerprint. The v0c archives have no WTV baseline.
- **Only if the original Task Agent must naturally continue:** its session, pending tools and delivery state must also be restorable. A controlled researcher-side workspace transition is a different experimental condition and must be named as such.

## Optional, if the required state is already lossless

A complete provider-ready request at the boundary, separately packaged tool history, a tar transport copy and a path-delta index make verification easier. They are not independent semantic stores. Existing root `request.json` demonstrates one request-archive form but does not supply ordinary-review state.

## Unnecessary / out of scope

No requirement database, evidence ledger, dependency graph, semantic classifier, verifier verdict, numerical confidence or model-visible checkpoint ID is needed. Historic reasoning chronology beyond the actual provider History and necessary receipts need not become permanent Supervisor state.

Checkpoint **does not equal memory, evidence ledger or semantic verifier**. Raw bytes, cursors and hashes are for offline research audit. The live Supervisor should continue to see only its authorized task evidence and the already-defined WTV mechanical transition view; a checkpoint should not add task hints or semantic labels to model input.
