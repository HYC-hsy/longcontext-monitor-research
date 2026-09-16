# Pinned upstream reuse

- pma_bm25.py: proactive-memory-agent/src/memory_agent/memory/bm25_search.py, commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd, https://github.com/yifannnwu/proactive-memory-agent, Apache-2.0 (PMA_LICENSE). Copied from our previously verified identical vendored source, no algorithm changes. Line endings / terminal blank lines normalized.
- liveplan_types.py, liveplan_formatters.py: Agent-Planner/plan_refiner/{types,formatters}.py, commit c16797a09b964f901b34fe3da430ee011a5cc660, https://github.com/Intelligent-CAT-Lab/Agent-Planner, MIT (LIVEPLAN_LICENSE). Only import path changed from plan_refiner.types to .liveplan_types. Line endings / terminal blank lines normalized.


No upstream prompts, providers, rule classifiers, datasets or benchmark answers are bundled. The wrappers outside vendor translate public events and natural private notes. Reusing these components is not a reproduction of either full paper.
# PMA two-phase candidate (2026-09-13, supersedes first-phase integration below)

The adapter now calls the unmodified `MemoryAgent.process` execution entry,
including both phase prompts, bank operations and reminder parsing. `context.py`
extracts `_get_memory_agent_context` and `_format_step_entry` verbatim from the
same revision's `src/memory_agent/memory_enabled_agent.py` into a dependency-free
class. Tests compare both method ASTs. Public host events are mapped to eight
task turns, bounded at the adapter, with separately labeled inspection receipts.
The existing monitor consumes reminders as leads, not automatic task input or
completion permission. The author's task scheduler/Terminus2 harness is NOT
copied; this is full memory-process reuse, not full original experiment reproduction.
Our transport reports swallowed phase failures and restores persistent history.

# Historical PMA first-phase candidate (2026-09-13)

`pma_memory/memory_agent.py`, `pma_memory/universal_memory.py`, and
`pma_memory/bm25_search.py` are unmodified (apart from line endings) copies from
https://github.com/yifannnwu/proactive-memory-agent at
89e5c0d6aadfe531a1aee42fd290d48be89973dd, `src/memory_agent/memory/`.
License: Apache-2.0; retained in `PMA_LICENSE`.
Author docstrings describe shared conversation, but actual process calls are
separate phase requests; those comments are retained for source fidelity.

Our `../pma_memory.py` reuses phase-one prompt construction, BANK_TOOLS,
operation execution, UniversalMemory and bank formatting/retrieval. It adapts
transport, bounded public inputs and atomic persistence. Our existing persistent
tool-using monitor replaces the original text-only phase two. We do not reuse
`MemoryAgent.process` or the author's synchronous task scheduler here, and do
not claim full PMA reproduction. The independent PMA baseline is unchanged.
