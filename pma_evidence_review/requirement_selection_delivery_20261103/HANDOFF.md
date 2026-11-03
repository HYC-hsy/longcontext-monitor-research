# Local P2 prototype handoff

Not uploaded. Worktree: `/Users/bytedance/Documents/Codex/2026-11-02/task/requirement-attributes`; local branch `pma/requirement-selection-view-v1`. Final local SHA is in the delivery reply. Base public P1 commit is `f656c6099f55db467987054e89bede4d4664c137`; its existing files are unchanged in this final candidate. Preserve the public P1 and DMS worktrees and all old real archives. This turn authorizes offline work only, with no push or real model/Task/evaluator execution.

In the existing PMA-compatible Python 3.12 environment:

```powershell
$env:PYTHONUTF8 = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
python pma_evidence_review/tools/run_p2_requirement_checks.py --report E:/PMA-private/p2-requirement-checks-NEW.json
python pma_evidence_review/tools/verify_requirement_delivery.py
```

The first command runs 153 strict fake P1 + default P2 + new P2 checks with a network guard. The second verifies the **unchanged published P1** material; the new local P2 files have their own MANIFEST.json, SOURCE_IDENTITY.json and OFFLINE_RESULTS.json in this directory. Do not substitute the old P1 source identity for the new 68-file P2 identity.

API usage, after existing P1 maintenance has durably completed, with an explicitly provided existing client:

```python
from p2_requirement_agent import RequirementSelectionAgent

p2 = RequirementSelectionAgent(p1=p1_agent, llm=existing_client)
report = await p2.select(
    observation=current_observation, entries=visible_steps, step_count=current_step)
# This prototype returns data only. It never sends messages to an Actor.
# A future host adapter must use its serial delivery lock and revalidate before enqueue.
if report['status'] == 'intervention' and p2.pending_refs_valid():
    original_text_delivery_json = report['delivery']
```

Use the stable P2 record.alias in both memory_read_source and the unchanged final XML. The raw memory_id is retained for identity/audit; it does not create another tool namespace. Initial BM25 groups can be a subset. memory_browse can query all frozen active items by requirement, flat or unclassified, and only complete returned records become selectable. Evidence reads are optional. P2H handles/cursors are session-scoped, cannot be selected, and cannot be carried into another invocation.

No-tools P2 uses one logical call; browsing/reading permits up to four total tool calls and two continuation rounds, with no tools on the final third turn. This budget is additional to P1, not secretly included in it. Long pages/groups/history may stay partial; do not infer complete coverage. Returned read errors or invalid output never become automatic no_intervention. Reopening after a crash creates a new P2 session; no persistent grant file is written.

Do not serialize the P1 bundle, snapshot links state, private profile, signing keys or unfiltered live reports into Git. Follow-up publication or real execution requires the parent thread's explicit authorization. No real experiment, real profile or existing-case rerun is needed to reproduce these offline results.
