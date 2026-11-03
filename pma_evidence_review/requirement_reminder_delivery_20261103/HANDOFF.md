# Generated-reminder interface delivery

Target: requirement-reminder-v1. Independent GitHub branch: `pma/requirement-interface-v1`. Fixed code commit: `6e4a90f10e505d5695b7cc054c908d0617421050`. Source/tests match the accepted local `e726265e7ce5efcb686f5236d5f9de0c83086905`. The final delivery reply pins the later documentation commit; INTERFACE_PUBLICATION_READBACK.json records source readback. PUBLICATION_READBACK.json describes only the older baseline.

Use the existing repository and PMA-compatible Python 3.12 venv. Fetch this independent branch and create a detached worktree with LF source bytes. Compare the printed delivery SHA with the final reply before proceeding; do not confuse the code-only commit with the final docs commit.

```powershell
$ErrorActionPreference = 'Stop'
$repoRoot = (git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Run from the existing repository.' }
$py = Join-Path $repoRoot '.venv\Scripts\python.exe'
if (!(Test-Path $py)) { throw 'Set $py to the existing PMA-compatible Python 3.12 venv.' }
git fetch origin refs/heads/pma/requirement-interface-v1
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed.' }
$deliverySha = (git rev-parse FETCH_HEAD).Trim()
Write-Output "Delivery SHA: $deliverySha"
$checkout = Join-Path (Split-Path $repoRoot -Parent) ('pma-interface-' + $deliverySha.Substring(0,8))
git -c core.autocrlf=false worktree add --detach $checkout $deliverySha
if ($LASTEXITCODE -ne 0) { throw 'Worktree creation failed; preserve existing work.' }
Set-Location $checkout
$env:PYTHONUTF8 = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
& $py pma_evidence_review/tools/verify_reminder_delivery.py
if ($LASTEXITCODE -ne 0) { throw 'Source/delivery byte verification failed.' }
$report = Join-Path $env:TEMP ('pma-interface-checks-' + [guid]::NewGuid().ToString('N') + '.json')
& $py pma_evidence_review/tools/run_p2_requirement_checks.py --report $report
if ($LASTEXITCODE -ne 0) { throw 'Strict offline checks failed.' }
$result = Get-Content -Raw -Encoding UTF8 $report | ConvertFrom-Json
if ($result.tests_run -ne 181 -or !$result.successful -or $result.errors -ne 0 -or $result.failures -ne 0 -or $result.skipped -ne 0) { throw 'Unexpected test inventory/result.' }
Write-Output "181/181 passed; report: $report"
```

Expected: 137 manifest files, 69 runtime source files; 181 strict fake tests, zero skipped. Do not run the historical 104-file P1 package verifier against this revision: it pins older shared LinkedSource bytes. Old runtime contracts are regression-tested. No profile, real provider, Task or native evaluation is needed and no old real groups rerun. Dependencies remain dirhash 0.5.0, litellm 1.106.6, pydantic 2.14.2 and httpx 0.28.1.


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

P2 reads are optional. It can browse flat, by requirement or unclassified, with an optional category=gap filter; counts refer to active records, not proven progress. The model passes the same stable M label as `entry` to locate sources; P1 delete also uses `entry`. Returned P2H handles are historical/session-scoped; they are distinct from current M labels. Raw IDs are retained in host logs/exports, not offered as another model-visible namespace. Identifiers quoted inside original evidence remain historical text. Missing evidence is explicit, not automatic success/failure or no-intervention. Memory is a fallible overview; no compulsory audits/checklist are introduced.

At most four P2 tool reads/two continuations, with final turn tool-free. P1 costs are separate; use exposed usage, actual call counters and wall time in any future separately authorized real test. Physical provider retries remain unknown. A crash/pending durable P1 cycle blocks P2 until host recovery resolves it; new P2 sessions do not inherit old grants. No whole-output directory or snapshot state may be committed: it may contain signing keys/private source data. This follow-up is published; no real model, Task or native evaluation ran.
