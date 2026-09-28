# Linux platform handoff — pending, not a PASS

Status: preparation only. Exact source and P remain unchanged. No authorized,
accessible Linux endpoint was identified in this development session. The local
Docker Linux engine is already known unavailable and was not retried. No remote
host was inferred from SSH known_hosts. Main-thread Linux access has not been
delegated to this worker.

Proposed target: a main-thread-assigned Linux worker with Bash and Python >=3.10,
and, for a later pilot, the existing no-network task-container/Unix-inference
transport. Distribution, kernel, Python, shell, installed dependencies, image
digests and mount layout are **pending host inventory**, not asserted facts.
Both arms must share them. Historical Linux equivalence is not required, but
differences must be recorded before a scientific launch.

## Existing materials are sufficient for the finite suite

Use a full Git checkout containing reviewed head
`8b67de43cebf51d73b4327065713428cb049f161` and anchor
`746a695adac4325d6440941d384d543d1364fef9`; do not copy a worktree's `.git`
pointer as a standalone source package. No duplicate archive is prepared:
the already-published objects, harness, policy and sanitized configuration
provide the required portable source materials.

Required repository-relative files/directories:

- `GenericAgent-main/monitor_agent_core/` at the anchor, with its complete local dependencies and Git objects;
- `method_discovery/diagnostics/m1_p_exact_acceptance_20260928/` at reviewed head;
- `method_discovery/diagnostics/rp_candidate_prototypes_20260927/P_POLICY.txt` (frozen c6e2 policy, no research overlay);
- `method_discovery/runs/dcec_v1_fyne_longrun_20260921/r1/monitor/resolved_model_config.json` (archived role settings, not live credentials).

From a clean reviewed checkout on the assigned host, choose absent sibling
directories. Provision requests >=2.28 and shortuuid >=1.0 from an existing
offline dependency cache; record actual versions. No install/network operation
was performed here.

```bash
git worktree add --detach ../m1-frozen 746a695adac4325d6440941d384d543d1364fef9
python3 method_discovery/diagnostics/m1_p_exact_acceptance_20260928/run_acceptance.py \
  --source ../m1-frozen --output-root ../m1-p-linux-offline-receipts
```

This is the existing finite acceptance set, not a new acceptance framework.
Fresh isolated interpreters validate source identity; fake send-boundary responses
and fail-closed HTTP/socket hooks capture actual attempts. Retain full requests,
receipts, source_identity, effective_config and counters, including any failures.
Do not convert an unrun command into a receipt.

The same host must additionally exercise the **real frozen Monitor dispatch**
`code_run` path with harmless Bash/Python directory/output checks, a nonzero exit,
and start/read session behavior. Record cwd, interpreter, shell, output and exit.
No project task is involved. These dispatch checks have not been run here.
The main thread's six successful Linux AnalysisSessions component checks are
supplied audit facts; they are not locally reproduced receipts or full M1/P
dispatch acceptance.

## Scope and differences

The published Windows traces remain valid only for their documented scope.
Linux full-suite and real-dispatch checks: **NOT COVERED / awaiting main-thread
platform review**. Native Linux must expose the frozen Linux/Bash schema, not
the Windows PowerShell schema. No source patch or schema substitution is proposed.

The future pilot's task workspace would be the pinned image's pristine `/app`,
with separate task-evidence and monitor-private mounts and existing no-network
transport. Exact mount and Python/dependency versions remain launch-readiness
items. AnalysisSessions alone does not establish task-container fidelity.

M1 anchor unchanged; P unchanged; D1 closed without C1 verdict; D2 deferred.
This handoff authorizes neither Linux access nor model/task execution.
