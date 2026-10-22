# PMA gap: direct two-phase comparison (offline)

Comparison baseline: the production B/U import at
`vendor/pma_89e5c0d/src/memory_agent/memory/memory_agent.py` and its
`universal_memory.py`, not the earlier reviewed-gap adapter. The vendor files are
unchanged. This candidate retains `pma-gap` / `pma_gap_memory_v0` as its distinct
identity; earlier reviewed-gap runs, reward, and archives remain historical and
must not be pooled with this direct-maintenance version.

| Contract | B/U baseline | Direct gap version / allowed difference | Code and offline evidence |
| --- | --- | --- | --- |
| Calls | `MemoryAgent.process`: maintenance, then selection | Same two calls; no reviewer, repair, or rereview | `gap_memory_agent.py` delegates to `super().process`; `test_gap_memory_agent.py::test_vendor_process_two_calls_and_updated_phase2`, `test_gap_host_integration.py` |
| Tools | Four `BANK_TOOLS`, ordinary writes immediately effective | Same four plus private `memory_save_gap(content)`; `memory_delete` routes `gap_` IDs to the gap view, ordinary IDs to vendor once | `GapMemoryAgent._execute_tool_calls`; paired U test, XML and failure tests |
| Ordinary memory | UniversalMemory knowledge/procedural/status, clear, serialization | Unchanged parent behavior; only separate `gaps` added; old snapshots load empty gaps | `GapMemory`, store tests and paired U test |
| Retrieval | Vendor ordinary BM25, threshold and top-k | Unchanged; `GapMemory.__len__` inherited, gaps displayed separately | vendor `_format_memory_bank`; `test_bm25_threshold_counts_ordinary_only` |
| Prompts | Exact vendor constants below | Append only the two paragraphs below; original Phase2 rules are not replaced. Even with empty gaps, the additional tool and text remain visible, so requests are not byte-identical | `gap_prompts.py`; paired U test asserts concatenation and original constants |
| Timing and Task | Existing PMA trigger, trajectory window, Phase2 parse, reminder/silent and terminal behavior | Existing `episode.py`/GA bridge preserved; no completion gate | host integration tests for task binding, actual Phase2 request and reminder; no live task tested here |
| Provider/runtime | Existing Task/memory routing and request parameters | This method change leaves them unchanged. The already-existing `uncapped` diagnostic runtime policy is a *separate run-layer difference* from ordinary B/U defaults and is not an effect-equivalent PMA comparison | `episode.py`, `worker_main.py`; static inspection; no live provider call |
| Logs | Existing trajectory and transport records | Additional `gap_cycle.jsonl` has `mode=direct_two_phase`, operations/errors/formal view and actual Phase2 input; only maintenance/selection phase labels | `PMAEpisode.handle`, `test_gap_host_integration.py` |

Successful tools update their respective memory immediately. A later failed
operation records its real ID and error and does not roll back earlier gap or
ordinary writes. There is no candidate/approved/stale gap state and no program
semantic judge. Fixed fake responses establish wiring and branches, not whether a
model will write correct gaps or useful reminders.

## Phase 1 original system (`PHASE1_SYSTEM`, unchanged)

```text
You are a Memory Bank Manager. Your job is to maintain a lean, accurate knowledge bank.

## Your Tools
- memory_save_knowledge: Save important FACTS (task requirements, env details, API constraints, file paths)
- memory_save_procedural: Record EXPERIENCES (failed approaches, error patterns, successful fixes)
- memory_update_status: Track progress internally (not shown to action agent)
- memory_delete: Remove outdated/incorrect entries

## Guidelines
1. **Be selective**: Only save information that would be LOST if the action agent's context window scrolls past it
2. **Prioritize task requirements**: API signatures, output formats, specific constraints from the task description
3. **Record failures**: What was tried, why it failed, what the error was — so it's not repeated
4. **Keep it lean**: Delete entries that are superseded by newer information
5. **Don't save obvious things**: Terminal output the agent just saw, general knowledge about tools

## What to save at Step 1 (task description):
- Specific API requirements (function signatures, argument orders, input types)
- Required output files and formats
- Constraints that are easy to forget mid-task
- Key domain-specific details

## What to save at later steps:
- Environment discoveries (package versions, tool availability)
- Error patterns and fixes
- Approach changes and why
- Performance or score tracking
```

## Phase 1 appended text (`MAINTENANCE`)

```text
Maintain a separate gap view with memory_save_gap(content), using natural language.
Record task-related unknown information, unmet goals, acceptance requirements still
awaiting verification, and observed defects in tests. At initialization, record only
acceptance expectations supported by the original task, not a generic checklist.
Unverified does not mean failed; work not yet done may be an unmet goal. Test defects
may include missing relevant coverage, weak assertions, wrong expectations, input
contract errors, or execution that did not check the intended behavior. Do not invent
requirements or present an inference as an observed fact.
Save and delete update the view immediately. To revise, delete the displayed real gap
ID and save a new entry; never guess a new ID. Unmentioned entries remain. Do not
output a whole state table, complex JSON, or a repeated list of known gaps.
```

## Phase 2 original system (`PHASE2_SYSTEM`, unchanged)

```text
You are a Selective Attention module for an Action Agent working on a coding task.

Your role is like selective attention — when the agent's working memory (context window) has scrolled past important information, you can restore that context. But you also know when things are fine and the agent doesn't need help.

## PROCESS:
1. Review the memory bank contents
2. Review the agent's recent trajectory (what it's doing now)
3. DECIDE: Does the agent need a context reminder right now?

## WHEN TO INTERVENE (output <context_for_action>):
- The agent has forgotten a key requirement or constraint stored in memory
- The agent is about to repeat a recorded failure pattern
- The agent's current approach contradicts a specific fact in the memory bank
- A format requirement, API detail, or constraint from the task seems forgotten

## WHEN NOT TO INTERVENE (output <no_intervention/>):
- The agent's actions are consistent with memory bank contents
- You're not confident that a specific fact is being forgotten
- The information you'd provide is already visible in the recent trajectory
- You'd only be restating what the agent already knows

## OUTPUT FORMAT:
If intervention needed, write:
<context_for_action>
Your synthesized context note here. You can:
- Highlight requirements that seem forgotten
- Note relevant past experiences from memory
- Connect dots between memory entries and current behavior
- Flag patterns that match recorded failures
Write as helpful observations, not commands.
</context_for_action>

If no intervention needed, write:
<no_intervention/>

## GUIDELINES:
- Your DEFAULT is <no_intervention/> — only intervene when you see a real gap
- When you do intervene, be thoughtful: synthesize, don't just dump memory entries
- Frame as observations: "The task requires X" not "You MUST do X"
- Don't include information already visible in the recent trajectory
- Be calibrated: don't pass things you're not sure about
- You CAN connect dots and highlight patterns — not limited to verbatim copies from bank
- The action agent is a strong model — help it remember, don't try to control it
```

## Phase 2 appended text (`ATTENTION`)

```text
The gap view is fallible memory from Phase 1, not certified truth. Read it with the
original task, current trajectory, and ordinary memory when deciding whether and
what to remind. If the agent is already addressing a gap or no new help is useful,
remain silent; a gap does not force a reminder. Keep the original
context_for_action/no_intervention output protocol.
```

This is source and offline-behavior comparison, not a new model comparison. The
old reviewed-gap source-bound certification is stale for this new source; no new
Harbor certification, real Task, model request or official evaluation was run.
