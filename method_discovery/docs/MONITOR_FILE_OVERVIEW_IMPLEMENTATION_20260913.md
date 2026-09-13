# File overview: small observation-entry revision

## Authorized scope and historical anchors

User approved replacing review_context with a stable file entry and restoring question/grounds-oriented continuity. No new decision mechanism, model, control loop or real run. Serves unsupported-closure research; no online checker.

Pre-change audit examined M3-D Fyne FDP7Urf decision_0008 (actual callback/menu conflicts), decision_0095 (silence during supported file-repository setup repair), decision_0096 (local URI success versus remaining root requirements), and current R3 dialogue L128/L140 (compilation promoted to global proof). Old decisions also include incorrect compatibility blocking and failed state writes; do not restore their schema or lifecycle machinery.

## Implemented

- decision_context.py removes composite semantic retrieval/read API, BM25 query composition and per-field event clipping. It now atomically refreshes monitor/overview.md before normal model requests and returns a short location notice.
- Overview contains a reference to model-owned working.md, full-task/raw-evidence/history/delivery paths, actual mounted workspace paths, last submitted correction, and latest four complete synopsis records with line locations. Earlier chronology is explicitly not covered by this four-record window and remains accessible. Synopsis is still navigation; no second-stage semantic summary or semantic correctness classifier is generated.
- working.md remains the single model-authored natural understanding. It is not copied into overview, renamed or overwritten by engineering. The overview explicitly tells the model to edit working.md rather than the regenerated navigation file.
- agent.py removes review_context tool registration and dispatch. With decision-context mode enabled, working.md and recent synopsis are no longer automatically injected as contents every request; the location notice replaces that path. Existing history/tool results stay; reads now use file_read/code_run.
- Prompt explains ongoing question, grounds, resolving observation, and local versus root completion in natural terms. No fixed fields, forced test checklist or mandatory tool call. Environment and generic tools retained.
- PMA two-phase execution and automatically visible PMA bank remain unchanged, including their limitations. This is not a claim to have eliminated all repeated judgments or solved final-boundary PMA freshness.
- Existing monitor_decision_context/GA_MONITOR_DECISION_CONTEXT configuration selects this entry. Internal name retained to avoid unrelated launcher changes, NOT a compatibility implementation of the retired tool. Configuration false disables file-entry behavior; old tool lives only in Git.
- Internal `_refresh_review_context` method and audit event named review_context remain: these are completion/advice updates and log records, not callable model tools. Removing them would break unrelated behavior.

## Preserved mechanisms

No production changes to runtime, interruption, follow/patrol, pending-completion checks, persistent provider history, compaction, independent credentials, PMA process, or raw archival timestamps. No author vendor modifications. Overview write failure reports stale/unavailable navigation rather than silently claiming freshness; original tools remain available.

## Steps and verification

1. Replace observation-entry implementation and agent wiring; py_compile succeeded. Code changes below 600 added/deleted lines.
2. Replace retired-tool tests with file-entry, full synopsis preservation, source/receipt, independent-task, failure visibility, same-session correction/follow and request-local input tests. Preserve unrelated author-source identity test. This test step also below 600 lines.
3. Nine focused groups initially 63 passed (before retaining the author-identity test). Expanded 16 groups: 165 passed, 5 failed in 13.54 seconds. All five failures are in test_clean_monitor_runtime.py due stale fixture constructor/adapter arguments (missing task_id/task_workspace), before modified observation code executes.
4. Verified the same five failures against HEAD versions of agent.py and decision_context.py loaded in memory from Git, without modifying working files: 5 failed, 5 passed. Thus not attributed to this change; left unchanged to avoid expanding scope. All other 160 expanded tests passed. diff --check succeeded.

Test command (GenericAgent-main, D:/python/envs/ga_bench/python.exe -m pytest -q): test_monitor_decision_context, test_monitor_pma_memory, test_monitor_pma_two_phase, test_monitor_follow_wait, test_monitor_correction_schedule, test_monitor_agent, test_monitor_core_independence, test_monitor_completion_interrupt_lifecycle, test_monitor_host_contract, test_monitor_advice_revision, test_monitor_feedback_focus, test_monitor_incremental_audit, test_monitor_inquiry, test_monitor_tool_feedback, test_monitor_provider, test_clean_monitor_runtime.

## Limits and stop

No API requests or real task launched. These are engineering checks, not evidence of better judgment. Model may still fail to read relevant originals, retain mistaken grounds, or under-read earlier reactions; a file is not itself a semantic solution. Last-four window is a visible convenience, not complete coverage since last observation. Existing PMA invalid-tool incident and completion-time comparison coverage are not repaired in this small change.

Next real comparison requires new run identity/source digest and explicit user confirmation. Inspect whether model uses overview/working understanding to find actual evidence, checks decision-relevant behavior, retains global scope, and avoids unbounded local repair. Do not accept lower time alone as improvement.
