# Reuse map

| Component | Classification | New-mode use |
| --- | --- | --- |
| Fixed PMA `MemoryAgent` phase builders, call seams, CRUD, parser, bank renderer and trigger | Direct upstream reuse | Existing `ComplementMemoryAgent` narrows status operations; separate phase orchestration and one frozen render are adapter changes. |
| Fixed PoS manager initialize/update, Sentinel, finite repair/re-audit, progress, health and recovery | Direct upstream reuse | One normal update per completed actor batch; no historical replay or extra scoring. |
| Fixed PoS `react_prompt._frontier_relevant_world` | Direct upstream reuse | Current-state panel projection; no replacement retriever. |
| `citation_fix.py` permitted source-field extraction | Existing baseline repair | New mode projects the same frozen history into actual audit-visible fields; task-only initialization is excluded. |
| `ComplementEpisode`, PMA provenance and advice receipt | Necessary host adaptation | Retain original Task history, independent state/bank, actual accepted-request boundary and partial-result export. |
| Phase 1 before PoS, frozen selected history in PoS updater/audit, Phase 2 after PoS | Candidate method change | This is an input and timing change, not a claim about released PoS or PMA behavior. |
| Complete recovery plus optional PMA advice in one temporary GA view | Candidate method change | PoS alone commits current state; PMA cannot gate completion or write status. |
| Removal of prior complement-only caps and pretrim | Candidate method change | Strict integrity and native projection remain; not a claim of known provider token capacity. |
| Generic `single_run` → Harbor/native-SHARED, independent PMA profile host, PoS worker, Task complete-response | Direct existing host path with mode identity adaptation | No new scheduler, evaluator or authorization service. |

Mechanical offline checks can establish request content, ordering, isolation,
receipts and cleanup. They cannot establish that a model used history correctly
or that this candidate improves outcomes.
