# evidence_package_v1 zero-model engineering audit

Status: **OFFLINE_BLOCKED; no real run authorized or started.** This is a default-off,
partly implemented candidate, not an accepted method or an executable pilot.
Baseline: `cea43088039154505a162514880af99acfc1c0c1` on
`crs-v0-20261007`; recent N run code `32eb30f9e0d6d4c95cc02d1afa6e594ad2e14202`.
The old archive and benchmark Task/evaluator are unchanged. Unrelated pycache remains.

## Actual implementation and reuse

`REUSE_MANIFEST.json` and `SOURCE_LOCK.json` record the fixed local and author
sources, licenses, Git blobs, call chain and reasons not to import incompatible
external runtimes. No CoverUp, Agentless, Haskell Build or PMA code was copied.
The implementation calls the existing MonitorAgent, run_review, provider,
workspace, spool and pilot preparation paths. Its added pieces are:

- A strict `monitor_evidence_package_v1` boolean, explicit
  `evidence_package_v1` profile variant, ASE+narrow enabled, CRS/RHR/RER disabled,
  projection off. Off/legacy/narrow profiles retain their old paths.
- Phase A exposes packet preparation, source investigation and the frontier,
  but not Task control. Its `packet_ready` has `executed=false/input_sent=false`.
  Phase B starts with fresh conversation History plus original task, packet and
  frontier page, then uses the existing delivery/control path.
- The versioned frontier retains distinct cases, leads, parent focus, receipt
  provenance, revisions, packet and findings. Ordinary Monitor file tools
  cannot write its sibling directory. Cursor revision changes fail visibly.
  Incomplete process receipts are not labeled behavioral verification.
- A/B share outer cycle and maintenance request counters; root cutover carries
  the aggregate. A stage History snapshot is read back before B begins.
  Existing provider pre-send capture checks stage system/tools/model and
  continuation/format-repair purpose. The real installed pilot analysis port is
  required; an explicit fake port is used only in tests.

These are real modifications to Supervisor/pilot research paths, not zero
production-code changes. `git diff cea43088..CODE_COMMIT` is reproduced in
the TXT audit packet. No benchmark Task, prompt, evaluator or old result changed.

## Deployment boundary that blocks an experiment

`pilot_entry._augment_compose` bind-mounts `run_root/monitor` read-write at
`/logs/agent/monitor` in the main Task/Monitor container. The frontier path
`monitor/.evidence_package_v1` is outside the sidecar's read-only
`monitor_private` cognition mount, but remains inside the Task container's
read-write monitor bind. A Task-side generic command could reach the would-be
canonical state. A direct `file_write` rejection is therefore insufficient to
certify a host-managed, non-overridable frontier. This is a concrete information
and integrity boundary, not a missing prompt. `MonitorRuntime` now refuses the
candidate before process start/provider send with the tested error
`Evidence package frontier is reachable from the Task container`.

Minimal next engineering decision: a trusted host-owned frontier service/port
with a Task-inaccessible store and request binding, or equivalent demonstrated
OS isolation. It must not give the model Docker control or Task RW access.
Until this is implemented and certified in the actual pilot, the candidate is
**not live-ready**. The direct-agent fake/Docker tests below do not bypass this
gate and are not deployment certification.

Other acceptance items still unverified or incomplete: generic private probe
classification does not yet distinguish actual matched test execution from
compile-only output for arbitrary commands; oracle/config/dependency change
invalidation has only narrow fixtures, not complete provenance coverage;
same-container Task access to the protected frontier is unresolved; deployed
first/next Supervisor requests were not executed through MonitorRuntime;
future false-premise and environment-blocked static cases lack certified
cutoffs. The candidate's `frontier_finding` validates ID existence, case/scope
equality, receipt completion and some receipt kinds but cannot programmatically
prove a natural-language causal claim or that a receipt actually covers the
asserted scope. These are not silently promoted to pass.

## Zero-model commands and observed raw output

Working directory `GenericAgent-main`:

```text
python -m pytest tests/test_evidence_package_v1.py tests/test_narrow_supervisor_v1.py tests/test_monitor_agent.py tests/test_monitor_provider.py -q -s --tb=short
......{"fake_request_stage": "A", "canonical_sha256": "5484012c57197e1d7a8efa6787646984bcde406aa9567bc3ab04afd5fbd596a9", "byte_count": 8276, "fields": ["max_tokens", "messages", "model", "stream", "system", "tools"], "message_count": 2, "tool_count": 9}
{"fake_request_stage": "B", "canonical_sha256": "8906078a5bc47cf481cd93ee7bb5d800642030013520a91fe332d3e395067ccf", "byte_count": 10591, "fields": ["max_tokens", "messages", "model", "stream", "system", "tools"], "message_count": 2, "tool_count": 12}
.........................................................................
79 passed in 3.46s
exit_code=0
```

Working directory repo root, with `PYTHONPATH` set to the actual
`GenericAgent-main` path:

```text
python -m pytest --import-mode=importlib method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012/test_profile.py method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012/test_bundle.py -q --tb=short
... [100%]
3 passed in 14.31s
exit_code=0
```

```text
python -m pytest --import-mode=importlib method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012/test_docker_candidate.py -q -s --tb=short
{"image_id": "sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1", "fake_provider_requests": 9, "host_receipts": 6, "task_write_denied": true, "private_copy_changed": true, "go_result": "build_without_running_tests", "behavior_verified": false, "bridge_closed": true}
.{"image_id": "sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e", "fake_provider_requests": 6, "host_receipts": 3, "task_write_denied": true, "private_copy_changed": true, "go_result": "no_test_files_compile_only", "behavior_verified": false, "bridge_closed": true}
.
2 passed in 44.43s
exit_code=0
```

All three pytest invocations also printed an atexit warning after the pass
summary: `PermissionError: [WinError 5]` while resolving the preexisting
`C:\Users\hsy\AppData\Local\Temp\pytest-of-hsy\pytest-951`; process exit
codes stayed 0. No unrelated temp/pycache was cleaned. The first Docker
tool output decoded the localized message with replacement characters:

```text
Error in atexit._run_exitfuncs:
Traceback (most recent call last):
  File "D:\python\lib\pathlib.py", line 215, in resolve
    s = self._ext_to_normal(_getfinalpathname(s))
PermissionError: [WinError 5] �ܾ����ʡ�: 'C:\\Users\\hsy\\AppData\\Local\\Temp\\pytest-of-hsy\\pytest-951'
```

The first Docker
fixture attempt lacked a `task_mounts['workspace']` entry; after that was
corrected, the Kitex expectation of `ok` failed because the command returned
`[no test files]`. The test was corrected to classify that as compile-only.
The complete earlier failing stdout/stderr was not retained; those attempts
are explicitly not counted as passing evidence.

The fake request hashes above are for the unit fixture's six-field payloads,
not a live resolved-profile request identity. They are not evidence that the
real endpoint would accept this candidate. The Docker tests performed 15
additional intercepted fake requests (Fyne 9, Kitex 6); the unit fake path
performed 13 (six A/B, five root, two maintenance): 28 intercepted fake
provider attempts across the cited final tests. No real endpoint was used.

## Source and configuration identities

The fixed Git source/author/license identities are in `SOURCE_LOCK.json`;
`REUSE_MANIFEST.json` links actual and rejected call paths. Local Python was
3.9.13 with pytest 7.1.2. Docker image IDs and RepoDigests were read from
local `docker image inspect`, not inferred from a mutable tag. The test
bundle stages the candidate module into the real isolated bundle, reads the
resolved `models.local.json`, and confirms the explicit S candidate flags.
It does not start a real MonitorRuntime; the launch gate above intentionally
blocks that. The fake unit requests omit profile-only thinking parameters,
so they are not passed off as the full deployed request.

The public effective profile uses `claude-opus-4-8`, max_tokens 8192,
adaptive/high, `timeout=120`, `read_timeout=300`, `max_retries=0`, TLS
verification, pilot incomplete-stream recovery true, ASE true, CRS/RHR/RER
false, projection off. Credentials and private endpoint strings are excluded
from the public identity. Task profile/Task inputs and scoring were unchanged.

## Future work is a draft, not authorization

`FUTURE_DIAGNOSTIC_MANIFEST_DRAFT.json` records two certified static cutoffs
and two missing case categories without inventing checkpoints. A later design
must freeze the same model, public information, tools, budget, order and
evidence rubric for current N versus this system candidate. Static diagnosis
would measure investigation quality, not live Task repair or task score.
Historical C01/C02 are exposed development fragments and not independent
tasks. No experiment was authorized by this document.

## Counts and disposition

Real Task model runs: 0. Real Supervisor model runs: 0. Real provider/API
requests: 0. Native evaluator: 0. Training/scoring-model calls: 0.
Intercepted local fake-provider requests in the cited final paths: 28.
Candidate live pilot starts: 0. The deployment mount boundary is a failed
mandatory gate, so there is no claim of complete offline acceptance or
method effectiveness. The independent research audit must decide whether to
authorize a bounded host-frontier repair and remaining acceptance work.
