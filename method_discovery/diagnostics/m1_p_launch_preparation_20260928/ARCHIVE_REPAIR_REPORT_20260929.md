# Final forwarding and archive-before-cleanup repair

Engineering only. No pilot rerun, model API, benchmark or verifier. M1 and
frozen P bytes are unchanged; precision budget wrapping remains disabled.

## Minimal production-adjacent delta

`launch_pilot.py` explicitly selects the existing neutral `original`
forwarding branch. Its final kwargs assert Task profile, 300 turns,
Monitor enabled and Monitor profile. `original` already is the native
adapter default; no checklist/oracle/task card is installed. The frozen
Task adapter therefore sets **the actual Task process** `GA_MAX_TURNS=300`
and `GA_MONITOR_ARTIFACT_DIR=/logs/agent/monitor`, not just Compose variables.

The opt-in `PilotArchiveAgent` delegates native setup/run unchanged and
wraps the existing environment `stop` boundary. Before native cleanup it
prepares the mounted logs or downloads `/logs/agent`, requires the principal
Monitor raw files and records their actual byte hashes. All other log
files, including delivery feedback, continuation and checkpoints, are
retained by the same full directory path. On archive failure it does not
call native stop/delete; it writes a host `archive_pause.json`. The entry
checks this before reading profiles or preparing another record.

This is deterministic host archive bookkeeping, not Supervisor semantic
state or a new mechanism. Default production launch and frozen M1 are not
modified. Future real execution requires new explicit authorization; old
authorization hashes do not authorize the repaired launcher.

## Executed finite checks

Raw originals: `archive_checks_20260929/`. Each case includes final Harbor
configuration, adapter receipt, native Task stdout/environment, Task and
Monitor histories/results, byte manifest and cleanup evidence.

| Check | Result | Primary evidence |
|---|---|---|
| Native Task + Monitor, M1 | PASS | `normal_m1/config.json`, `agent/output.txt`, `agent/pilot_final_adapter.json` |
| Native Task + Monitor, M1+P | PASS | `normal_p/config.json`, `agent/engineering_env.json`, gateway requests |
| Archive readable after normal cleanup | PASS | both `agent/pilot_archive_receipt.json`; hashes rechecked after cleanup |
| Archive failure retains containers | PASS | `archive_failure/agent/pilot_archive_failure.json`, `retained_inspect.json` |
| Archive failure stops next admission | PASS | `test_archive_pause.py`, actual unittest execution (2 passed) |
| Harbor Task time limit | PASS | `timeout/result.json`: real `AgentTimeoutError` at 30 seconds; host archive survives |
| Outer exception | PASS | `outer_exception/result.json`: injected exception after actual native Task termination; archive survives |
| Declared P delta | PASS, limited | `comparison.json`: first full request differs only in P + explicitly mapped original-task filename; every request has exactly 0/1 P and same tools |
| Abrupt host kill / OS crash | NOT COVERED | no claim that a cleanup hook runs after process death; correct host log mount preserves already-written bytes |
| 300-response exhaustion | NOT EXERCISED | final config, instance and real subprocess all verified at 300; no 300-call fake loop added |

Later asynchronous histories are preserved, not normalized away or claimed
identical. Fake choices are not evidence of model capability. Normal M1's
first check captured environment in actual tool output; later checks also
saved `engineering_env.json` from that same Task tool execution.

The actual chain is `launch_pilot.main -> pinned run_proof -> Harbor CLI ->
PilotArchiveAgent -> native agentmain + native M1 Monitor -> Harbor cleanup`.
Test-only seams supply a short synthetic task, empty `/app` bind, finite
120-second wrapper / 30-second timeout case, fake upstream, disabled
verifier and no live OTel collector. No Kitex/Ratatui project is executed.
The cached image supplies Linux/runtime libraries only. Both services have
network-none; native isolation checks execute, and fake HTTPS accepts only
`offline.invalid`. Fake usage is explicitly test data. Five completed
checks captured 37 fake requests; actual model requests are zero.

Two earlier engineering failures are preserved under
`earlier_engineering_failures/`: (1) the first fake script did not recognize
the pending handoff, and used an unnecessarily large image workspace;
(4) a test assertion used mixed-case Docker project labels instead of the
actual lowercase labels. Neither is a scientific record. The latter's
containers really remained; inspect and narrowly scoped cleanup receipts
are retained. Publisher path-length/UTF-8 compatibility errors were fixed
without changing source bytes. The early large workspace expansion is not
republished; existing local originals remain. The complete successful small
fixtures are published. No historical pilot containers were deleted.

## Reproduction (fresh output directories, virtual credentials only)

Use existing authorized Docker Linux and runtime layout documented in
`EXECUTION_HANDOFF_20260929.md`, and an exact M1 detached source.
Run with Python 3.12+ (the installed Harbor environment provides this):

```text
git worktree add --detach <m1-source> 746a695adac4325d6440941d384d543d1364fef9
python check_archive_launch.py --supervisor-source <m1-source> --output-root <new-normal>
python check_archive_launch.py --supervisor-source <m1-source> --output-root <new-p> --policy
python check_archive_launch.py --supervisor-source <m1-source> --output-root <new-failure> --failure archive
python check_archive_launch.py --supervisor-source <m1-source> --output-root <new-outer> --failure outer
python check_archive_launch.py --supervisor-source <m1-source> --output-root <new-timeout> --failure timeout
python -m unittest discover -s method_discovery/diagnostics/m1_p_launch_preparation_20260928 -p test_archive_pause.py -v
```

The script paths above are in this directory. Actual local commands used
`bench_runtime/m4/harbor-env/Scripts/python.exe`, exact source
`E:/LongContext_m1_frozen` and distinct owned temporary outputs. Each raw
`actual_harbor_command.json` preserves the final unabridged invocation.
`file_manifest.json` is derived from original copied bytes; `.gitattributes`
disables text conversion. Private real profiles and credentials are not
part of this projection.

Old four-record disposition is separately recorded in
`method_discovery/runs/m1_p_pilot_20260929/AUDIT_ADDENDUM_20260929.md`;
old raw records and missing-archive declarations are unchanged. Engineering
PASS does not establish P effects or repair the old scientific provenance.

STOP: no real record is launched after these checks.
