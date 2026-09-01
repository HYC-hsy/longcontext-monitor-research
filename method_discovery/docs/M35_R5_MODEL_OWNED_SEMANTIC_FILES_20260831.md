# M3.5 R5: Model-Owned Semantic Files and Generic Atomic Tools

Date: 2026-08-31
Status: engineering-complete; cumulative real-task validation pending

## Why R4 was replaced

R4 correctly identified that the monitor needed durable task understanding, evidence
revision, bounded continuity, and active retrieval. Its concrete interface still asked
the model to produce runtime-facing obligation identifiers, structured deltas, and
binding-sensitive updates. That made the model spend attention on an integration
protocol and allowed natural-language understanding to fail at the model-to-runtime
boundary.

R5 replaces that interface rather than retaining a compatibility path. The old R4 code
and tests remain recoverable from Git history, but are not part of the active runtime.

## Active architecture

The same persistent monitor now has three complementary forms of state:

1. A stable system context containing its role, no-checker boundary, human-style control
   principles, generic observation capabilities, intervention contract, and original
   public task.
2. One continuing provider conversation carrying the monitor's current cognition across
   wakes. Exact older dialogue is externalized only during patrol after the soft bound;
   focused attention and open repair episodes are protected from compaction.
3. A model-owned natural-language filesystem under the run artifact directory:
   `task/original_task.md`, freely revisable `state/` files, and freely revisable
   `evidence/` files. The initial files are navigation aids, not a required ontology.

The runtime supplies only generic atomic operations:

- list files with a stable order, glob, and simple continuation offset;
- read a bounded line view with a full-file hash and continuation offset;
- search regular-expression text with glob, bounded context, and continuation;
- create, patch, replace, append, or prepend one natural-language file operation after
  reading its hash when the file already exists;
- inspect the public task, trajectory, workspace, tests, diffs, prior decisions, repair
  state, and externalized history through existing read-only evidence tools.

The model-visible edit contract is deliberately flat: `mode`, `hash`, optional `old`,
and `content`. It does not expose batched edit objects, runtime ids, or separate
old/new field vocabularies. Whole-file replacement lets the monitor reorganize its own
cognition instead of accumulating append-only patches merely because the interface is
awkward.

The runtime enforces path safety, optimistic concurrency, atomic replacement, and
append-only versions. It does not interpret task semantics, assign requirement ids,
bind paraphrases, decide which field a statement belongs in, or infer completion.

## Preserved research mechanisms

- M1 persistence survives as the natural task model, working state, evidence navigation,
  persistent monitor history, and active reconstruction tools.
- M2-C scoped semantic-impact revision survives as a semantic rule: contradictory or
  invalidating public evidence must revise/reopen the affected understanding, retain the
  source anchor, and preserve the prior belief in version history. It is no longer tied
  to a fixed `workspace_delta` or obligation-id protocol.
- M3 adaptive patrol is always active. A wake contains navigation metadata rather than a
  pushed semantic packet; the monitor chooses what to retrieve and when to sleep again.
- M3 A/B/C/D remain independent candidate switches for decision focus, qualitative
  information value, a bounded discriminating inquiry, and inquiry lifecycle control.
- Repair episodes, sparse user-like intervention delivery, focused follow-up, local
  release, and the separate root-completion boundary remain active.
- Ordinary task execution remains concurrent and never waits for a patrol judgment.

## Removed active interfaces

- fixed obligation arrays and model-maintained ids;
- `workspace_delta` and structured semantic-object mutation;
- positional/fuzzy natural-language binding in the runtime;
- separate M1/M2/M3.2/M3.5 enable flags for mechanisms that are now mandatory parts of
  the cumulative parent;
- legacy packet-review and synchronous SILENT/HOLD paths;
- obsolete real-task conditions that differed only in names after their mechanisms became
  core behavior.

## Engineering evidence

- GenericAgent full test suite after the atomic-tool simplification: 297 passed.
- Harbor adapter and active real-task runner regression set: 85 passed.
- Prompt-surface checks cover stable policy, turn-zero bootstrap, ordinary wake, tool
  continuation, and completion wake; implementation-stage labels, old schemas, framework
  names, and replacement characters are excluded from model-visible text.
- Regression coverage includes turn-zero initialization, versioned file edits and
  conflicts, persistent history, bounded externalization, open-repair protection, active
  trajectory/test/diff/history retrieval, repair/release behavior, root completion,
  non-blocking task progress under monitor failure, and next-safe-boundary intervention
  delivery.
- The current M3 real-task gate exposes only the meaningful M2-C and M3 A/B/C/D
  conditions; retired M3.1/M3.2/M3.5 labels can no longer generate identical fake
  comparisons.

No complete real task was run for this migration. These results establish engineering
integrity and mechanism availability, not task-quality improvement or candidate
acceptance. The next cumulative real-task run remains subject to the independent launch
gate.
