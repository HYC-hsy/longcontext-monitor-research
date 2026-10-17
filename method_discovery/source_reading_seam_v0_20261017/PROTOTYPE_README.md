# Source-reading seam v0: offline, Phase-1-only

This is a bounded information-flow prototype, not a semantic result. It adds one
fallible source-reading call before original PMA Phase 1, then runs original PMA
Phase 2 using the actually committed bank. The readout is **not independently
injected into Phase 2**. No Task continuation, real inference, provider request,
deployment, or interaction with a user's computer occurred.

## Run

From this directory:

```sh
env -i /usr/bin/python3 -I -S run_fake.py > results.json 2> results.stderr
```

No installation is needed. The existing shared-filesystem PMA checkout, reviewed
harness, fixed public evidence archive, and six archived input-view pairs are
dependencies; `PROVENANCE.md` and `reuse_manifest.json` identify them. No fetch or
download fallback exists. A changed executable source or absent dependency stops
the run. This is runnable in the current shared filesystem, not a standalone
redistribution of the full historical archive.

The retained run has 257 named interface assertions and empty stderr. That count
is a coverage inventory, **not an effectiveness measurement**. Every model-shaped
reply and bank decision is scripted. The same supplied helper/PMA answers can
make an arm look successful or unsuccessful without testing any LLM judgment.

## Five bounded conditions

1. `ordinary`: zero helper calls; original PMA Phase 1 and Phase 2.
2. `source_reader`: one isolated source read; its prose and a generic fallibility
   instruction are appended to Phase 1 only.
3. `exposed_reader`: the same instruction, word limit, and Phase-1-only placement,
   with the full original narrative and original PMA-selected bank view also visible to the reader.
4. `raw_replay`: zero helper calls; append the complete exact task to Phase 1.
5. `source_replay`: zero helper calls; append exactly the deterministic packet the
   isolated reader would receive to Phase 1, including all commands/results.

Both replay controls concern source placement/repetition, not a pure extra-call
comparison. `source_replay` repeats observations as well as the task, addressing
the observation-scope case that task-only replay does not match. The common
ordered-update suffix remains present in all conditions; when updates are
supplied, `source_replay` also repeats them inside its exact packet. This is
explicit, tested repetition. Phase 2 has neither replay nor helper suffix.

All arms preserve the full original task/observation and keep the original bank
data intact. Original PMA retrieval settings, including its default BM25
prefilter above 50 entries, are unchanged. The exposed reader receives the same
formatted bank view selected by original PMA for this observation, not extra
hidden entries. The retained historical banks are below that threshold, and
their original Phase-1 prompt bytes reproduce exactly. A large-bank fixture
checks parity with original default retrieval and retention of all stored entries.

With the same scripted reader output and Phase-1 decisions, the isolated and
exposed arms produce identical downstream wire payloads. Their reader inputs
have different lengths; matched instructions/call counts are not matched tokens,
latency, cost, or semantic difficulty. No real token/latency data were measured.

## Enforced source boundary

The projector is the exact existing 123-line `decision_phase2_views.py` retained
in the audited implementation diff. Its EB output is reproduced byte-for-byte
against all six archived F/EB pairs, covering 43 recorded steps.

The isolated packet contains only:

- The complete original task, without normalization or clause selection
- The ordered user-update strings supplied by the host
- The full ordinary-window trajectory after the existing EB field projection
- Mechanical window information and explicit missing-context limitations

The packet strips the projected PMA bank/prefix and task suffix. It excludes
outer `Agent Analysis`, outer `Terminal Output.content`/working-memory text,
and inherited bank content. No observation is chosen for seeming decisive.
No additional truncation or semantic cleanup occurs.

Raw command JSON is retained exactly. Complete `tool_results` values are
preserved, with the same deterministic JSON reserialization as the audited EB
implementation. **Self-written claims, comments, assertions, or copied memory
inside command arguments/results remain.** This is channel isolation, not pure
external evidence or complete narrative removal. A printed “all passed” is not
certified by the packet builder.

The strict archival grammar rejects ambiguous or unsupported structures. A
projection failure is logged and falls back to ordinary PMA; it is not silently
repaired and does not claim a successful isolated read. This archived-text seam
does not establish a general online host boundary.

The public three-case archive contains no authenticated update stream, so those
runs supply an empty tuple. Only explicitly synthetic tests supply update
strings. The host must establish their authority; this adapter cannot authenticate
the user or infer updates from actor narrative.

## Unchanged PMA behavior and receipts

Pinned PMA `89e5c0d6aadfe531a1aee42fd290d48be89973dd` supplies the constructor,
bank representation/CRUD, both prompt builders, `process` chronology, structured
tool execution, XML fallback, and advisory tag parser. Its vendor bytes are not
patched. The new subclass hooks only add the Phase-1 supplement and record calls,
actual bank snapshots, and failures.

Phase 2 uses the original builder after Phase 1. Its system is unchanged; its
only common addition, if present, is the exact ordered-user-update source suffix
also used by the earlier adapter. Readout text may appear there if original
Phase-1 CRUD actually committed that text. This is not a second readout channel.

Original CRUD is non-atomic. One successful write can survive a later failed
delete or parser error. The prototype records `partial_or_failed`, reads back
the actual bank, and preserves original Phase-2 fallthrough. It never describes
that outcome as a successful correction. A receipt about applied operations
does not certify truth, completeness of intended repair, or safe retirement.

There is no retirement engine beyond original CRUD/readback, no automatic
claim detector, no new memory ontology, no extra tools, no confirmation truth
label, no Task completion lock, and no Task-side approval state. An unavailable
old source does not mechanically delete its memory entry. A bad helper has no
direct CRUD capability; a fallible Phase-1 model could still adopt it, which
this scripted prototype cannot rule out.

## Adversarial interface coverage

- Wrong helper and embedded tool-call text cannot directly overwrite memory
- Missing old support does not automatically invalidate retained knowledge
- Helper errors, timeout, malformed/empty/oversized output, and tool-bearing
  replies log fallback and still attempt both PMA phases
- Unsupported projection grammar never silently pretends source isolation
- Partial CRUD and upstream parser errors retain and expose actual committed state
- Reader packet rejects score/gold/case-label arguments and input subclasses;
  evaluation labels remain only in the test trace, never runtime packet metadata
- Original structured tools, XML fallback, advisory/silence parser remain intact
- Large-bank selection matches upstream defaults without deleting stored entries
- One synthetic three-wake replay verifies committed-state carryover/revision
- No Task execution, delivery, or gate is introduced

These are structural claims. Scripted no-ops demonstrate that the interface
permits rejection/retention; they do **not** demonstrate that a model rejects the
wrong helper, understands missing evidence, narrows an overclaim, preserves
useful facts semantically, or makes helpful advice. Source text can itself
contain words such as “score” or “gold”; it is preserved, not censored. The
positive allowlist excludes independent researcher metadata channels.

## Execution boundary and artifacts

All transports must be exact `ScriptedCall` instances reused unchanged from
`reference_revision_v0`. Arbitrary callables, subclasses, shared helper/PMA
transports, and hidden helpers in zero-helper conditions are rejected. There is
no provider selection or live-mode flag.

The runner inherits the existing clean-environment / isolated-Python staging and
audit pattern. Pinned PMA files are copied unchanged to a temporary staging
directory. A synthetic `shortuuid` shim supplies fixture IDs. Runtime hooks
restrict network sockets, processes, environment mutation, file opens/writes,
and non-stdlib/provider imports. Only the authored harness and pinned reviewed
code execute. As before, this is an audited local harness, not a security sandbox
for arbitrary malicious Python. Archived Task commands are data and never run.

- `adapter.py`: new Phase-1 seam, packet boundary, original CRUD/readback receipts
- `input_views.py`: byte-identical existing EB implementation
- `reference_adapter.py`, `reference_evidence.py`: byte-identical authored reuse
- `checks.py`: all synthetic semantic replies, scenarios, and assertions
- `run_fake.py`: pinned-source, restricted offline runner
- `results.json`: exact wire requests, scripted raw replies, state snapshots,
  parser outputs, failure receipts, and named assertions
- `summary.json`: compact packet sizes and call counts for retained traces
- `PROVENANCE.md`, `reuse_manifest.json`, `manifest.json`: source/adaptation hashes
- `PMA_LICENSE`: unchanged upstream Apache-2.0 license

The scope stops at this seam. It does not integrate PoS, alter the ongoing PoS
run, run GA, deliver an advisory, measure Task behavior, or establish novelty or
effectiveness. Real paired inference and end-to-end continuation need separate
authorization, frozen evaluation, and independent semantic assessment.
