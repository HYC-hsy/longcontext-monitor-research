# Pinned upstream reuse

- pma_bm25.py: proactive-memory-agent/src/memory_agent/memory/bm25_search.py, commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd, https://github.com/yifannnwu/proactive-memory-agent, Apache-2.0 (PMA_LICENSE). Copied from our previously verified identical vendored source, no algorithm changes. Line endings / terminal blank lines normalized.
- liveplan_types.py, liveplan_formatters.py: Agent-Planner/plan_refiner/{types,formatters}.py, commit c16797a09b964f901b34fe3da430ee011a5cc660, https://github.com/Intelligent-CAT-Lab/Agent-Planner, MIT (LIVEPLAN_LICENSE). Only import path changed from plan_refiner.types to .liveplan_types. Line endings / terminal blank lines normalized.


No upstream prompts, providers, rule classifiers, datasets or benchmark answers are bundled. The wrappers outside vendor translate public events and natural private notes. Reusing these components is not a reproduction of either full paper.
