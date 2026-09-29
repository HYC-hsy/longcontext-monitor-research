# Authorized pilot: startup failure, panel paused

Preparation: `337758d23d8f03d017dfbbca3fcc321e6dfc5ba7`.
The four-record authorization was received; no method/configuration changes
were made. Twenty participating experimental Python files were checked against
the approved Git bytes, allowing LF/CRLF representation differences only.
Git and runtime SHA256 identities are in `../execution_authorization_20260929.json`.

| Record | Run ID | Status |
|---|---|---|
| kitex-m1 | pilot-20260929-01 | One invocation; failed before model requests in original model-identity resolver |
| kitex-m1-p | pilot-20260929-02 | Not started; panel paused |
| ratatui-m1-p | pilot-20260929-03 | Not started; panel paused |
| ratatui-m1 | pilot-20260929-04 | Not started; panel paused |

## Original failure

`launch_pilot.main -> run_proof -> preflight -> m4.resolve_model` runs a
short-lived `docker run --rm` with Task source mounted read-only at
`/opt/genericagent`. The source export does not contain `temp/`.
Frozen Task `agentmain.py:98`, at the start of `GenericAgent.__init__`, attempts
`os.makedirs(os.path.join(script_dir, 'temp'), exist_ok=True)` and gets:

`OSError: [Errno 30] Read-only file system: '/opt/genericagent/temp'`.

Source: exported pinned `run_harbor_tb2_m4.py::resolve_model` (lines 193–218),
and Task `agentmain.py::GenericAgent.__init__` (line 98). These are startup
plumbing, not Supervisor semantic failure or a scientific P effect.

The existing thin-entry fake test replaced the `run_proof` execution boundary;
the Linux fake-container check directly exercised the Monitor/transport path.
Neither established that this full original model resolver could initialize
against a fresh read-only Task export. Their published limited PASS scope is
not evidence of this resolver passing.

## Evidence and limits

- `failure_stderr.txt`: exact stderr text transcribed from the execution tool
  result, session 88566, chunk `1aeea3`; exit code 1. No evaluator was invoked.
- `launch_identity.json`: byte-for-byte copy of the original generated identity.
- Local original output remains at `../formal_pilot_20260929/kitex-m1/`.
  It contains exported launcher/Task/M1 sources and secret-bearing private
  configuration, so the whole directory is **not** published.
- Only `launcher`, `m1-source`, `task-source` directories were created. No
  `formal` directory, scientific Task/Monitor trajectory, gateway request log,
  provider usage or verifier result was produced.
- Zero scientific model requests: failure precedes model-client initialization
  and the scientific launch. This is a control-flow fact, not a fabricated
  zero-valued usage receipt. Tokens/cost/actual model identity: not applicable;
  there were no actual provider requests from which to validate those fields.
- Model-resolver container used `--rm` and exited. No pilot container remains
  running. Unrelated historical stopped containers were not removed.

## Stop boundary

No record restart, alternate output directory, source/runner patch, environment
repair, model smoke call, evaluator run or subsequent record launch was made.
Private profiles were assembled only from the two existing named account
configs; keys/endpoints are not archived. Frozen common parameters were retained.
M1, Task source, P and default production remain unchanged. D1 remains closed;
D2 remains deferred. Await main-thread decision on this startup defect; do not
reinterpret this as a completed four-record scientific panel or a P result.
