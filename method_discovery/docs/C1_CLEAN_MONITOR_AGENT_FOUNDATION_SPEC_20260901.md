# C1 Clean Monitor Agent Foundation Specification

Date: 2026-09-01  
Status: user-authorized foundation specification; implementation not started

## 1. Purpose and boundary

This document freezes the clean engineering substrate on which later method innovation will be built.
The product is an independently designed Monitor Agent for long-horizon task drift. GenericAgent (GA)
supplies reusable agent-runtime primitives; it is neither launched unchanged nor presented as the method.
The accumulated M0--M3.5 monitor supplies behavioral evidence and regression cases, but is not the clean
implementation parent.

C1 deliberately does **not** select a wiki, graph, semantic-cell representation, evidence-revision
algorithm, or learned compression policy. Those are research mechanisms to add only after the foundation
can run, observe, interrupt, continue, and remain silent correctly.

The foundation must preserve the paper boundary:

- target representation omission and unsupported closure in long-running Agents;
- use public task, action, tool, workspace, test, diff, and monitor-history evidence only;
- never depend on an online checker, native verifier, gold answer, or future trajectory;
- run the task Agent continuously and keep monitor latency outside its ordinary critical path.

## 2. Evidence anchor: what human FBR actually did

The design was re-anchored to the original FBR 2.43 human trajectory, decisions, interventions, and report,
not reconstructed from later prompts. Its effective loop was:

1. retain the root task while allowing broad, nonuniform ordinary progress;
2. notice a high-information public event, especially intent, new/changed tests, execution evidence, or a
   completion claim;
3. inspect the actual tests, code, diff, and trajectory needed to judge that event;
4. identify one material conflict between the public contract and the Agent's current causal interpretation;
5. request a discriminating public probe or a concrete correction rather than demand generic reflection;
6. stay nearby after correction and inspect the Agent's understanding, next intent, test oracle, and result;
7. intervene again only when the correction is misunderstood, evidence remains non-discriminating, or a
   new material conflict appears;
8. release the local investigation when its evidence is sufficient, without declaring the root task done;
9. at proposed completion, reconstruct root coverage and allow only when no known material discrepancy
   remains.

The same evidence rejects three tempting implementations:

- enumerating and verifying every UNKNOWN;
- treating every failed first attempt or imperfect artifact as drift;
- remaining in an unbounded high-quality code-review loop after the current decision no longer changes.

## 3. Architecture decision

The clean system has two independently running agents:

```text
Task Agent process/session
    performs the public task continuously

Monitor Agent process/session
    runs a monitor-specific role on reusable GA runtime primitives

Thin controller
    archives public observations, schedules monitor wakes, and executes the monitor's
    two control actions; it never judges task semantics
```

An independent spawned worker process is the default host for Monitor Agent. This is an engineering
isolation choice, not a second semantic agent: one persistent monitor identity and one monitor model session
survive across wakes. A provider hang, tool timeout, crash, or restart cannot freeze Task Agent.

The controller carries no semantic packet and performs no hard-coded drift classification. It transfers only
task identity, monotonically increasing observation cursor, lifecycle signals, and the Monitor Agent's chosen
control action.

## 4. Reuse map: GA runtime primitives

### 4.1 Reuse directly or extract with behavior preserved

| GA capability | Foundation use | Reason |
|---|---|---|
| provider session and native tool client | dedicated Monitor Agent session | mature provider, streaming, retries, telemetry |
| `agent_runner_loop` protocol | monitor tool/reason/action loop | avoids another hand-written JSON review loop |
| low-level `code_run` process runner | implementation basis for monitor analysis execution | supports arbitrary inspection scripts, streaming output, timeout, stop |
| provider history and log writing | monitor conversation continuity and audit | mature persistent conversational substrate |
| history-transform telemetry | cost and information-loss measurement | required before later memory innovation |
| `GenericAgent.abort()` | low-level Task Agent cancellation primitive | identical primitive used by user-facing Stop |
| task/session restoration patterns | crash recovery reference | preserves provider history across host reconstruction |

"Reuse" permits extracting a neutral primitive from a GA module. It does not require inheriting the entire
`GenericAgent` or `GenericAgentHandler` class.

### 4.2 Reference, but do not inherit unchanged

| GA behavior | Why it cannot be copied unchanged |
|---|---|
| `GenericAgentHandler` | contains executor tools, write authority, user questions, browser actions, memory reminders, and task completion behavior |
| file read/write path resolution | joins paths to cwd but does not establish the monitor's read-only task boundary |
| default `code_run` cwd handling | suitable for a trusted executor; monitor needs writable analysis space separated from read-only task evidence |
| `<summary>` working-memory anchor | useful navigation signal but too short and lossy to be authoritative task cognition |
| fixed 7/10/25/175-turn reminders | executor heuristics, not autonomous semantic monitor scheduling |
| `trim_messages_history` | acceptable temporary baseline, but destructively truncates linear history and is not the paper memory method |
| ordinary task completion semantics | Monitor Agent completes a review/wake, not the supervised root task |

## 5. Reuse map: accumulated monitor

### 5.1 Preserve as required behavior

- turn-zero initialization from the immutable public task;
- one persistent monitor identity and conversation across wakes;
- autonomous, nonuniform patrol timing;
- active inspection instead of receiving full semantic packets passively;
- tests as provisional executable interpretations, not automatic truth;
- public-evidence-only judgment and explicit uncertainty;
- intent-level correction and continued observation after intervention;
- local release distinct from root-task completion;
- explicit root completion review;
- task-hash-bound restoration and auditable decisions/telemetry;
- monitor failure isolation from Task Agent.

### 5.2 Preserve as evidence, not foundation implementation

- model-owned semantic files and their version archive;
- scoped semantic-impact revision from M2-C;
- cognitive checkpoint and archived inspection receipts;
- patrol/focused attention terminology;
- challenge, residual, release, and reopen concepts;
- evidence provenance and versioned state.

These may inspire or become later research mechanisms, but C2 must not silently import them. Each later
mechanism needs an independent switch and real-task evidence.

### 5.3 Delete from the model-visible foundation

- M0/M1/M2/M3 candidate names and feature flags;
- mandatory JSON decision envelopes and protocol retries;
- obligation ids and model-maintained runtime ids;
- fixed `intervention_mode`, epistemic classification, severity, residual, release, and anchor fields;
- specialized inspection-tool explosion;
- deterministic semantic packet construction or a third observation/index layer;
- intervention coalescing that requires repair episode ids;
- legacy HOLD/SILENT/RELEASE synchronous approval semantics;
- compatibility branches whose rejected versions already remain recoverable in Git.

Deleting these surfaces must not delete the behaviors in section 5.1.

## 6. Observation contract: exactly two evidence layers

The supervised task exposes exactly two observation layers:

### Layer 1: chronological public synopsis

An append-only, cursor-addressable stream containing one bounded synopsis for each public Agent decision
step plus minimal facts needed to locate it: task turn, announced intent/summary, tool names, available
outcome status, and raw-log span/reference. The intent synopsis is published as soon as the model response
and tool choice become public, before the selected tool runs; later public outcomes advance the cursor
without requiring a semantic packet. GA's model-authored `<summary>` is the initial source, but it is never
treated as proof or authoritative task state.

Layer 1 answers: "What changed, and where should I look?"

### Layer 2: original public evidence

The immutable original task, complete public Agent log, public tool calls/results, live task workspace,
tests, diffs, command output, and generated artifacts.

Layer 2 answers: "What actually happened, and does it support the judgment?"

No deterministic semantic index or packet sits between these layers. If Layer 1 proves too lossy, its
synopsis format may be made richer; a third authoritative observation representation must not be added.

Monitor Agent's own conversation and writable analysis files are its cognition, not a third supervised-task
observation layer.

## 7. Monitor Agent workspace and tools

Monitor Agent receives a private writable analysis workspace and a read-only view of Layer 2. It never
writes production files, tests, Task Agent history, or raw evidence.

The initial tool surface is intentionally small but does not force routine file work through generated code:

1. **file read**: read a bounded range from either the read-only task evidence view or the private monitor
   workspace. The same simple interface serves original tasks, logs, code, tests, and monitor-authored notes.
2. **file write**: create, replace, append, or prepend a file only inside the private monitor workspace.
3. **file patch**: replace one exact existing text span only inside the private monitor workspace. This is the
   preferred operation for local cognitive updates because it need not rewrite an entire note.
4. **analysis code execution**: Python and the platform shell, based on GA's process runner; scripts run from
   the private monitor workspace and may read the task evidence view. They may list/search many files,
   grep/tail logs, compare files, parse tests, create temporary indexes, and save intermediate analysis in
   the monitor workspace.
5. **wait**: finish the current review without intervention and choose when to inspect again during patrol.
6. **intervene**: submit one natural user-like correction. The controller invokes the existing Task Agent
   abort primitive, waits for the active generation/tool boundary to unwind, and supplies the correction to
   the same Task Agent session.
7. **allow completion**: available only while reviewing an explicit root-completion proposal; it cannot end
   ordinary execution or a monitor review opened for another reason.

Directory traversal, cross-file search, log following, diff composition, and custom analysis initially remain
ordinary code-execution tasks rather than separate specialized tools. Convenience tools may later be added
only if traces show that this general surface is ergonomically inadequate; they cannot reduce access to the
original evidence or reintroduce a semantic packet/index layer.

Path safety is an engineering invariant. Prompt instructions alone are insufficient: task evidence is
exposed through an OS- or adapter-enforced read-only view, while generated scripts and analysis outputs are
confined to Monitor Agent's writable workspace. `file_write` and `file_patch` reject task-evidence paths in
the implementation before any filesystem operation; `code_run` receives the same enforced separation.

## 8. Minimal control-action protocol

Semantic reasoning and intervention wording remain natural language. The model does not fill a task-state
schema. Only the action boundary is typed:

- `wait(after_turns)`: no user-like message; remain in patrol and wake after the chosen amount of public
  progress. The value is the Monitor Agent's estimate, not a classifier decision by the controller.
- `intervene(message)`: immediately request Task Agent cancellation and deliver `message` as the next
  user-like input in the same task session.
- `allow_complete()`: accept only the currently pending root-completion proposal.

After `intervene`, the controller enters **close-watch delivery**, not a semantic repair state machine. Every
new Task Agent synopsis wakes the same Monitor Agent until it calls `wait`. The Monitor Agent may inspect raw
evidence and intervene repeatedly. This operationally reproduces "do not leave after the first correction"
without requiring repair ids, residual fields, or deterministic release rules.

User Stop has higher authority than monitor intervention and always terminates the task. Monitor failure is
recorded as failure; it never fabricates silence or blocks Task Agent.

## 9. Minimal lifecycle

### 9.1 Initialization

1. start Task Agent and Monitor Agent concurrently;
2. write the immutable public task to Layer 2;
3. wake Monitor Agent at turn zero to understand the task and orient its own conversation/workspace;
4. Monitor Agent chooses its first `wait` distance; Task Agent never waits for initialization.

### 9.2 Patrol

1. Task Agent continues and appends synopsis plus raw evidence;
2. controller wakes Monitor Agent at its chosen cursor distance, explicit root completion, or recovery from a
   missed schedule;
3. Monitor Agent reads Layer 1 and autonomously decides whether and how to inspect Layer 2;
4. it calls `wait` or `intervene`.

### 9.3 Intervention and close watch

1. `intervene` calls the existing abort primitive;
2. current Task Agent generation/tool execution is cancelled using GA's established stop path;
3. the correction becomes the next user-like input in the same provider/task history;
4. every subsequent public turn wakes the same Monitor Agent;
5. repeated misunderstanding permits another immediate intervention;
6. when the Agent's interpretation and direction are reasonable, Monitor Agent calls `wait` and patrol
   resumes.

### 9.4 Root completion

Root completion is always a monitor wake. It may be a bounded controlled transition, but ordinary task turns
remain asynchronous. The monitor reconstructs coverage using public evidence and either calls `intervene`
or `allow_complete`. Native verification remains post-termination only.

### 9.5 Failure and shutdown

- monitor timeout/crash: record, restart from durable monitor history/artifacts, never stop Task Agent;
- Task Agent provider/tool failure: visible public evidence, not automatically judged as drift;
- user Stop: terminate Task Agent and Monitor Agent, preserve archives;
- successful root completion: close both agents after durable telemetry flush.

## 10. Foundation history and compression policy

C2 initially uses GA's linear provider history and transform telemetry as a deliberately strong, ordinary
Agent baseline. The immutable public task and all Layer-2 evidence remain externally recoverable. The
foundation must record every history transformation, characters/tokens before and after, and removed ranges.

No claim is made that GA history trimming solves monitor memory. Specifically:

- turn-zero task understanding must remain recoverable after it leaves foreground history;
- close-watch continuity must not be silently cut mid-investigation;
- the old monitor's "never compact focused repair" rule is not inherited because it can grow without bound;
- the old 5k continuation note, latest-eight-message tail, and unused target threshold are not inherited;
- no new semantic compression is introduced before the clean baseline runs.

Nonlinear semantic memory, wiki-like organization, evidence-carrying revision, and decision-relevant
foreground selection begin only after this foundation passes C4. GA-as-monitor with linear history becomes
a strong baseline against which those mechanisms must improve quality/cost.

## 11. C2 component boundary

C2 should introduce only the following new implementation components:

1. `MonitorAgent`: owns the monitor role, provider session/history, and one review-at-a-time GA-derived loop;
2. `MonitorHandler`: exposes bounded file reading, private file writing/patching, analysis execution, and the
   terminal control actions;
3. `MonitorWorkspace`: private writable analysis root plus read-only task evidence view;
4. `MonitorController`: thin lifecycle/IPC shell; semantic-free and nonblocking;
5. deterministic fixtures covering role isolation, tool permissions, persistent history, and action receipts.

C2 does not yet implement production Task Agent interruption or real-task execution. C3 integrates the two
agents and the abort/continue loop after C2's identity, tools, and history are proven.

The existing `abort()` entry point is reused, but its cancellation latency is not assumed correct merely
because the UI exposes Stop. C3 must test cancellation during provider streaming and during tool execution.
If the current flag is observed only after another stream chunk, the neutral GA cancellation primitive must
be strengthened before claiming intent-level intervention latency.

## 12. C1 acceptance audit

- [x] new method remains an independently designed Monitor Agent;
- [x] GA is a reusable substrate, not the claimed contribution;
- [x] successful old-monitor behavior is preserved without inheriting its schema;
- [x] online checker and hidden verifier remain forbidden;
- [x] ordinary Task Agent execution stays concurrent and nonblocking;
- [x] observation remains two-layer and active;
- [x] universal analysis capacity is retained without production write authority;
- [x] routine file access and private cognitive editing do not require generated code;
- [x] monitor silence and intervention are minimal action interfaces, not semantic classifiers;
- [x] compression is explicitly deferred as a measured research problem rather than accidentally frozen;
- [x] C2 and C3 remain separately testable implementation stages.
