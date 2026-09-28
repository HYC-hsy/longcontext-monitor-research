# Experimental launch preparation — finite offline receipt

**NOT AUTHORIZED TO EXECUTE THE PILOT.** No Docker, model service, benchmark or
verifier was used. M1, P, task choice/order and historical archives are unchanged.
This is launch/resource plumbing, not evidence that P selects useful observations.

## Entry and source separation

`prepare_bundle.py` provides the opt-in `bind_roadmap_builder()` seam at the
existing `run_proof -> build_bundle` boundary. The check imports the actual
reviewed Roadmap runner and local script dependencies from exported Git objects,
calls its bound builder, then starts a fresh host child through the resulting
GA adapter prelude into native M1 `runtime._worker`. It does **not** run
`run_proof`, task preflight, Harbor, container init or Task Agent execution.
Virtual credentials are used throughout. These preparation bundles deliberately
cannot provide real inference: gateway destinations are `offline.invalid`.

- Task source: `8b67de43cebf51d73b4327065713428cb049f161`, exported whole
  GenericAgent runtime tree; no dirty current files or developer `mykey.py`.
- Supervisor: complete `monitor_agent_core` from
  `746a695adac4325d6440941d384d543d1364fef9`, copied into the ordinary bundle's
  package location. All original files are immutable; runtime and Git-blob
  hashes are separately retained. Export/worktree LF/CRLF equality is checked.
- Runner, GA adapter and isolated transport: reviewed `8b67de43...` Git objects;
  actual script imports/hashes and bundle transport hash appear in raw captures.
- P: c6e2 neutral `P_POLICY.txt` bytes and reviewed `experimental_adapter.py`.
  Neither policy nor native system is rewritten.
- Copied-bundle-only preludes in `agentmain.py` and `ga_monitor_adapter.py`
  install source checks, common resource accounting and optional P after native
  Monitor construction. No default checkout/runner behavior is modified.
  Existing Task source bodies stay pinned; preludes are explicitly declared
  source overlays, not concealed under a claim of unchanged bundle bytes.

The standard source mount remains `/opt/genericagent-source` (returned to the
Roadmap caller); a proposed read-only client profile mount is
`/pilot-config/models.json`, and a shared resource-audit mount is `/pilot-resource`.
Every future record must use a distinct record ID and fresh task/private state,
but the **same panel budget directory**. Container mounts are declarations only.
The test runtime directory and Python home are placeholders, not Linux runtime
identities. Full online launch integration, actual task worker environment and
mounts cannot be accepted from these host subprocesses.

## Reproduce the no-model check

In a full repository checkout containing both commits, create a clean detached
M1 worktree in an absent directory. No private absolute path is required:

```powershell
git worktree add --detach ../m1-frozen 746a695adac4325d6440941d384d543d1364fef9
python method_discovery/diagnostics/m1_p_launch_preparation_20260928/run_checks.py --supervisor-source ../m1-frozen
```

The same Python command is usable on an authorized Linux host; it has **not**
been run there. Requires existing requests/pytest/shortuuid dependencies.
`run_checks.py` captures actual stdout/stderr and exit code. The fixed check
uses fake HTTP only, denies parent/child HTTP-session and socket connections,
and executes real frozen file_read/file_write/wait. Fake response/usage and
original Task native transport/parser are clearly tagged engineering fixtures.
The Task transport test uses no Task tools or agentmain task loop.

Published run: **5 tests passed**, pytest exit 0. Two host children captured
six Supervisor and two synthetic Task transport requests; actual external/model
requests were zero. `pytest.stderr.txt` preserves an existing Windows pytest
atexit cleanup PermissionError for an older temp directory. Current dependency
inventory reports shortuuid not installed; inactive vendor paths were not tested.
Neither limitation is hidden behind an overall platform PASS.

## Acceptance scope

| Item | Status | Raw evidence / limitation |
|---|---|---|
| Explicit M1 identity, no current-source fallback | PASS (host) | `offline_receipts/{baseline,candidate}.json`: binding, modules; missing/wrong source checks and source rejection |
| Real pinned Roadmap bundle boundary | PASS (host) | Same captures: `launch_imports`, `binding`, `compose`, refreshed `isolation_identity`; no real run_proof/container |
| Native worker initialization and ordinary tools | PASS (host) | Three Supervisor requests per arm, private audit files, state update and real wait |
| M1 versus M1+P request difference | PASS (host) | `parity.json`, full raw payloads; one P insertion; only explicitly recorded full bundle-root identity normalization |
| Task source/config and request parity | PASS for source and synthetic transport | Actual native Task parser request retained; fixed synthetic session/device IDs; Task executor NOT COVERED |
| Source/policy failure closed | PASS (host) | `source_failure.txt`, `policy_failure.txt`; no transport on rejection |
| Unified logical/attempt/token resource guards | PASS for checked paths | `budget_synthetic.json`, full captures and tests; limitations below |
| Six task originals, byte equality | PASS | `task_source_index.json`, originals; no reformatting |
| Linux full M1/P, image digest, runtime, dependencies, actual mounts | NOT COVERED | No authorized usable Linux task worker; no repeat Docker attempt |
| Full online Task/Monitor processes, tool-time and waiting accounting, launcher watchdog termination | NOT COVERED | Requires the real common Linux launch/transport and budget approval, not host fake-worker substitution |
| Monetary hard cap | NOT IMPLEMENTED / NOT APPROVED | No rates or authorized expenditure; ledger explicitly records false |

The previously accepted Windows finite M1/P control/continuation suite is not
reopened or re-labeled Linux PASS. This new short check is only the opt-in launch
seam. No claim that Fyne capability was reproduced or that P improved behavior.

## Resource semantics and remaining execution decisions

Archive `roles.task_agent` and `roles.supervisor` supplies explicit profiles:
native_claude_cc_vibe_opus48 / claude_monitor_opus48, both claude-opus-4-8.
Supervisor adaptive/high, temperature 1, output 8192, context 200000, timeout
30/read 300 are retained. Task archived output 64000 is **explicitly replaced
by proposed common 8192**; archived retry=8 becomes proposed common retry=2.
These shared experimental budget changes are not historical Fyne settings or
P-exclusive benefits. Full effective settings are in each capture's binding
and role profiles. No independent verifier/model role is instantiated.

`resource_budget.py` is common deterministic resource bookkeeping, not another
semantic memory. A shared file lock serializes record/panel admission and usage
updates; it must remain research/runtime audit, never a prompt source. No task
truth, evidence adequacy or completion judgement is produced.

- Ordinary review, continuation and format repair all enter Monitor `_request`
  and count toward 120/record. Review ordinary calls cap at native 20; Task native
  raw_ask counts toward 300/record. Four-record ceiling: 1680 logical admissions.
- Each `_request_once` or native Task HTTP send is a separate attempt. Three
  attempts/logical admission cap => 5040 attempts for the batch. Retries do not
  reset or create free logical budget. Native retry receipts remain in audit.
- Anthropic input, cache-read, cache-creation and output are retained separately.
  Input cap applies to their processed-input sum (not equal-dollar pricing).
  Proposed record 4M input/1M output; batch 16M/4M. Before a logical admission,
  reserve the caller's per-attempt context/output estimates multiplied by the
  permitted attempt count, against both scopes and other pending envelopes.
  Estimates are not trustworthy provider-enforced upper bounds: admission
  protects declared envelopes, not a guarantee that actual consumption cannot
  exceed the cap. Retries use the frozen envelope, not fresh logical allowance.
- Missing usage, failed attempts with unknown usage, or actual receipt exceeding
  reservation/cap cause explicit blocked-resource state and no later provider
  admission. Known portions remain recorded; unknown is not imputed as zero.
  A missing sent-attempt usage receipt pauses the entire panel (including
  retries of other pending calls); finish retains its unresolved envelope,
  received usage and failure type. Known portions remain accounted separately.
  Per-attempt estimate breach pauses the panel at receipt time even below total
  caps; already sent requests may still finish and retain their results. No
  automatic unpause or corrective model call is provided.
  Monitor wrapper settlement precedes return of a successful completed response.
  Task raw_ask is streaming: content may already have been yielded upstream
  before settlement raises BudgetStop. The synthetic wrapper order test proves
  this limitation; it does not prove absence of earlier Task actions or retract
  delivered content. Full Task control-loop stop order remains NOT COVERED.
  There is no automatic allow_complete or repair call.
- Clock spans: logical call begins at wrapper admission and ends after native
  parsing/retry/error cleanup. This includes retry/backoff, not wire-only latency.
  Record and panel clocks begin at first admission. Review clock begins at its
  first Monitor admission; maintenance is attributed to its current review ID.
  Proposal: 600s/review, 9000s/record, 43200s/panel; cumulative Monitor provider
  span 1800s/record and Task 7200s. Check on admission/receipt, not a claim of
  hard preemption of a blocked network read or running tool. In-flight overshoot
  remains possible and must be archived; later admission stops.
- Actual Task watchdog (7200s), Supervisor analysis commands (60s default/120s
  maximum, 1200s cumulative proposal), evaluation ceiling (1800s), delivery/wait
  clocks and host cancellation must still be confirmed through the Linux launch
  path. Those controls are not implemented by inventing synthetic task receipts.

Thus the checked logical/token accounting is executable, but **a complete hard
wall/tool/money budget is not claimed**. Platform readiness and main-thread
resource-policy review remain prerequisites for freeze/authorization. Do not
interpret passing engineering tests as permission to spend $400.

## Pilot boundary retained

Order: Kitex M1; Kitex M1+P; Ratatui M1+P; Ratatui M1. Fresh independent
workspaces/history/notes; no R, new repeats, tuning or fabricated failure.
Historical exposure retained. Observation taken/seen/used, grounds/control,
delivery/recovery, native outcome, false release/block, reasonable unresolved,
cost/latency and opportunity to exercise P remain separate research judgements.
No selection difficulty means no P-effect evidence; no adequate-evidence release
opportunity means no relaxation validation. Native scores alone are insufficient.

D1 remains closed, no C1 verdict/retake. D2 DEFERRED / NOT AUTHORIZED.
Stop here for main-thread launch/platform/budget review, not a model smoke run.
