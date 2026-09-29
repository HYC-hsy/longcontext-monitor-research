# Local Linux launch preparation — ready for execution confirmation, not running

This supersedes the *platform absent* and *precision budget required* parts of
the older readiness/proposal. It does not alter M1/P, historical records or the
scientific pilot. P remains unproven. D1 closed; D2 deferred.

## Actual platform and finite evidence

Docker Desktop was started from its existing `E:/Docker/Desktop` installation.
Engine: 29.6.1, Linux x86_64, WSL2 kernel
`6.18.33.2-microsoft-standard-WSL2`, 12 CPUs, approximately 15.6 GiB RAM.
No remote/paid host, installation, image build or pull was needed.

| Item | Status / original receipt |
|---|---|
| Both frozen task image IDs match existing proposal | PASS; image IDs below and `platform_receipts_20260929/docker_recovery.json` |
| Real no-network main containers + Unix gateway channel | PASS; four **engineering configurations**, not four scientific records; `linux_fake_launch_20260929_a/*/container_inspect.json` and compose logs |
| Source/runtime/profile mounts | PASS for mounts actually listed in each compose/inspect; source `/opt/genericagent-source`, runtime `/opt/m4-runtime`, profile `/pilot-config/models.json`; Unix channel read-only in main |
| Exact M1 worker imports | PASS; `*/logs/capture.json` modules plus `*/bundle/source/pilot_binding.json` Git/runtime hashes; no slot branch |
| Provider → local HTTP → Unix socket → frozen gateway route/Handler | PASS; client payloads equal `*/gateway_logs/requests.json`; only upstream HTTPS connection replaced by fake response; both containers network none |
| Native Linux Bash/Python tools, file read/write, updated DCEC view and receipt reuse | PASS; actual command output/result files and private audit in each `logs/engineering-fixture/monitor`; not whole Task execution |
| M1/P parity | PASS; `summary.json` records exact session-ID mappings; raw payloads retained; only one frozen P body differs in system; same Task payload |
| Common budget-wrapper bypass | PASS; binding false, no resource ledger, native Task transport not wrapped; existing budget artifacts untouched |
| Regression/locked entry | 18 passed, exit 0; `platform_receipts_20260929/regression.json`; four plan outputs and execute-without-authorization rejection in `launch_plans.json` |
| Future entry preparation, both policy settings | PASS with `run_proof` execution boundary replaced by a deterministic test callback; `platform_receipts_20260929/thin_entry.json` and `thin_entry_p.json`; original bundle builder and substrate checks executed, not the full Task loop |
| Full scientific Task Agent loop, real HTTPS/auth/model response, verifier | NOT EXECUTED; these are the authorized pilot itself, not claimed fake-model success |
| All project offline dependencies | Cache presence observed, NOT claimed complete. Dockerfiles contain ignored build/fetch failures. No project test/build/verifier executed here. |

Five scripted Supervisor completions plus one synthetic native Task transport
completion per engineering configuration: 24 captured requests, **0 real model
requests**. Fake usage explicitly labelled. Main exited 0; Compose aborts the
long-lived gateway at main exit (gateway 137 in cleanup is retained in raw logs).
All created engineering containers/volumes were removed with project-scoped
`compose down -v`; host raw artifacts remain. No historical/user volumes removed.

`bash -lc` reset image PATH during initial inspection; ordinary inherited PATH
located Go/Rust. Native M1 runs `bash <script>`, not login Bash, and that actual
dispatch succeeded. No textual path rewriting or source patch was introduced.

## Common configuration for confirmation

- Task: exact source `8b67de43cebf51d73b4327065713428cb049f161`, profile
  `native_claude_cc_vibe_opus48`, model `claude-opus-4-8`, adaptive thinking,
  temperature 1, context 30000, output 64000, connect timeout 60/read timeout 300.
- Supervisor: exact M1 `746a695adac4325d6440941d384d543d1364fef9`, profile
  `claude_monitor_opus48`, model `claude-opus-4-8`, adaptive/high, temperature 1,
  context 200000, output 8192, connect timeout 30/read timeout 300.
- Both retain archived `max_retries=8`. This is retry count, not eight extra
  logical reasoning stages. Raw native attempts/usage remain authoritative;
  missing usage stays unknown. No fallback model, R, boundary/slot or selector.
- Native DCEC + semantic continuation enabled, view 4000; seven native Linux
  tools. Native ordinary review limit 20; Task max turns 300. No new per-record
  Supervisor 120-call/token/precision-money wrapper ceiling.
- Native online Task wall 7200 seconds; task.toml native post-termination verifier
  timeout 1800 seconds; normal runner cleanup grace retained. Four sequential
  records imply up to 8 hours online plus 2 hours verifier allowance, excluding
  setup/cleanup. This is not a new universal runtime theorem or a dollar cap.
- Common task resources from task.toml: 2 CPUs, 4096 MiB RAM each; sequential
  execution, fresh image/container, independent workspace/history/working state.
- No-network main, capabilities dropped, no-new-privileges; only fixed Unix
  inference/OTel channel. Real gateway keeps original HTTPS/auth/TLS path; fake
  gateway is used only in the engineering check, never in `launch_pilot.py`.
- Source/layout changes are explicit bundle-only prelude, exact M1 package copy,
  frozen P adapter and budget-enabled switch. Default production files untouched.
- Monetary cap not implemented, $400 not approved. Existing model account and
  permission for these four long records require explicit user/main-thread
  execution confirmation. No purchase/new worker is required.

Frozen task images:

- Kitex `sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e`
- Ratatui `sha256:6f9da0a2c21293e8e0d2bac70947260da9edd9e3de0bcb09af3008218bbcc18d`
- Existing gateway Debian ID
  `sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171`

Initial `/app` snapshot is pinned by the immutable image ID, not the target
release's solution. Ratatui manifest reads 0.21.0; Kitex go.mod is the original
`github.com/cloudwego/kitex` snapshot. No prior repaired workspace is mounted.

## Reproduction and future commands

No-model Linux check (fresh absent output path required):

```powershell
python method_discovery/diagnostics/m1_p_launch_preparation_20260928/check_linux_launch.py `
  --supervisor-source E:\LongContext_m1_frozen --output-root <new-engineering-output>
```

`launch_pilot.py` is an experimental thin entry into pinned `run_proof`, not a
new executor/control loop. It exports pinned scripts/adapters and copies the
byte-frozen existing OTel configuration/Harbor patch files (not Git blobs at the
Task commit; indexed in `launch_substrate_originals/source_index.json`),
passes the original runner the existing task assets/runtime, and binds the exact
M1/P builder. Research arm names remain host metadata; native run IDs are neutral
`pilot-20260929-01` through `04`. No implicit current GA imports or real-key search.

For each record, **without `--execute`**, inspect the plan (already captured):

```powershell
python method_discovery/diagnostics/m1_p_launch_preparation_20260928/launch_pilot.py `
  --record kitex-m1 --supervisor-source E:\LongContext_m1_frozen --output-root <new-pilot-root>
```

After a separate main-thread execution confirmation, the intended commands use
the same entry/options plus `--execute --authorization <approved-json>
--profiles <private-two-role-json>`, in this exact order:

1. `--record kitex-m1`
2. `--record kitex-m1-p`
3. `--record ratatui-m1-p`
4. `--record ratatui-m1`

Authorization is **not supplied**. Entry refuses before profiles/container access
unless the artifact approves the record and binds M1 commit, Task commit, frozen
P SHA and actual launcher SHA. Private profiles must preserve every declared
common archived field, with only approved provider credentials/HTTPS endpoint
and transport verification information added. No credentials are archived here.
Private source/gateway configuration created during a future real launch must
not be published with keys. No authorized record overwrites an existing root.

Original run_proof retains native concurrency, wait/intervene/root identity,
watchdog, post-termination verifier and OTel/result archival. The full online
branch has not been executed; local branch/transport checks are not a model-effect
claim. Do not automatically start a smoke call, fifth record, retry-to-success,
or record-level tuning. The next decision is explicit four-record execution
confirmation, not another precision-budget project.
