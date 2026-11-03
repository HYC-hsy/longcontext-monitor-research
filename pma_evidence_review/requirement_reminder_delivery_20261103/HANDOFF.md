# Local generated-reminder prototype

Authoritative target: requirement-reminder-v1. Local worktree is `/Users/bytedance/Documents/Codex/2026-11-02/task/requirement-attributes`, branch `pma/requirement-selection-view-v1`. Final local SHA is in the delivery reply; code-only identity is in SOURCE_IDENTITY.json. Public branch: `pma/requirement-reminder-v1`. Source byte verification pins `c5674ca8085cf912046029a487a970401af51c32`; the final delivery reply gives the later fixed documentation SHA. Earlier selection-only delivery material is historical; use this directory for current generated output and checks.

In the existing repository, use the known PMA-compatible Python 3.12 venv. This script resolves and detaches one exact fetched delivery commit; compare its printed SHA to the final delivery reply (or set $deliverySha to that reply's fixed SHA). Preserve LF bytes for source/manifest checks:

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
$py = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'Set $py to your existing PMA-compatible Python venv.' }
git fetch origin refs/heads/pma/requirement-reminder-v1
$deliverySha = (git rev-parse FETCH_HEAD).Trim()
Write-Output $deliverySha
$checkout = Join-Path (Split-Path $repoRoot -Parent) ('pma-reminder-' + $deliverySha.Substring(0,8))
git -c core.autocrlf=false worktree add --detach $checkout $deliverySha
Set-Location $checkout
$env:PYTHONUTF8 = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
& $py pma_evidence_review/tools/verify_reminder_delivery.py
$report = Join-Path $env:TEMP ('pma-reminder-checks-' + [guid]::NewGuid().ToString('N') + '.json')
& $py pma_evidence_review/tools/run_p2_requirement_checks.py --report $report
& $py pma_evidence_review/tools/verify_requirement_delivery.py
```

Expected: the new target's byte verifier passes; 167 strict fake tests pass; the last command verifies the unchanged 104-file published P1 package. This directory's MANIFEST.json/SOURCE_IDENTITY.json cover the new target (69 runtime source files); do not treat the old selection-only manifest as current. No private profile, real provider, Task or native evaluation is needed. These checks do not rerun old real experiment groups. If the existing venv lacks the already documented dependencies, report the import failure rather than lowering strict checks.

Existing committed P1 → generated P2 only:

```python
from p2_requirement_reminder import RequirementReminderAgent
p2 = RequirementReminderAgent(p1=p1_agent, llm=p1_agent.llm)
report = await p2.remind(observation=current_observation, entries=visible_steps, step_count=step)
# report.delivery/context_for_action is a synthesized plain note, not alias JSON.
```

Explicit independent composition (does not start Task):

```python
from p2_requirement_reminder import RequirementReminderPipeline
pipeline = RequirementReminderPipeline(p1_agent)
result = await pipeline.run(visible_steps, observation=current_observation,
                            step_count=step, cycle_id=unique_cycle_id)
# Host code must keep its delivery lock and revalidate before any later enqueue.
if result['should_inject'] and pipeline.p2.pending_refs_valid():
    note_for_action = result['context_for_action']
```

The P1 process() guard remains; use maintain() or the explicit pipeline. Do not replace SYSTEM alone on the old selector: generated reminders use different rendering, original PMA parsing, plain-note delivery and whole-bank/ref validation. Verbatim selection remains a separate compatibility class, not a fallback for malformed generated output.

P2 reads are optional. It can browse flat, by requirement or unclassified, with an optional category=gap filter; counts refer to active records, not proven progress. The same stable M alias locates sources. Returned P2H handles are historical/session-scoped; raw memory IDs/P1 aliases do not create another entry namespace. Missing evidence is explicit, not automatic success/failure or no-intervention. Memory is a fallible overview; no compulsory audits/checklist are introduced.

At most four P2 tool reads/two continuations, with final turn tool-free. P1 costs are separate; use exposed usage, actual call counters and wall time in any future separately authorized real test. Physical provider retries remain unknown. A crash/pending durable P1 cycle blocks P2 until host recovery resolves it; new P2 sessions do not inherit old grants. No whole-output directory or snapshot state may be committed: it may contain signing keys/private source data. Publication was authorized and completed; real model execution and actual Task integration were not authorized for this round.
