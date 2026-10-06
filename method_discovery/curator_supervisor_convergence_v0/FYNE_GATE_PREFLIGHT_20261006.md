# Fyne gate — offline runtime-configuration preflight

Status: configuration-only freeze; no Task Agent, Supervisor model, provider, verifier, or Fyne run was started. Candidate source: `0a34cd63332b66b74cc21f00b6cb35803dd8648b`. Task in scope: `roadmapbench:fyn-2.2.0-roadmap` only.

## Supervisor profile resolution

`agentmain.py` reads `GA_MONITOR_CONFIG=claude_monitor_opus48` and calls `ga_monitor_adapter.monitor_profile`. That loader uses `MONITOR_CONFIG_FILE` if set; otherwise it prefers the deployed `GenericAgent-main/monitor_agent_core/models.local.json`, then the sibling `monitor_config/models.local.json`. The previous isolated ASE Fyne bundle contains the deployed file at `E:\ase_v1_core_private_20261006\bundle_ASE\source\monitor_agent_core\models.local.json` (SHA-256 `80aec26730854ade3e113c1806a03bdbdb03c2bfe055f64c336213bb71af7e3a`). Its private source profile is `E:\ase_v1_core_private_20261006\launch_ASE\monitor_config\models.local.json` (SHA-256 `8b31658406214ccdbc8213b8bf9fc2558171c6b7a2476adbea6fcc4e2c254c17`). The isolation bundler copies that profile into the deployed file while replacing credentials and endpoint with local-channel transport. No credential or endpoint is reproduced here.

The candidate `0a34cd6` has **not** been deployed to a new bundle. In the current source worktree, neither default profile location exists; `GA_MONITOR_CONFIG` by itself would not resolve there. A future candidate deployment must explicitly bind/copy the frozen private profile and verify its identity. This preflight does not authorize or claim a runnable experiment.

Resolved non-secret Supervisor values from the private source profile, with code defaults applied:

| Field | Value |
| --- | --- |
| profile / model | `claude_monitor_opus48` / `claude-opus-4-8` |
| provider / API mode / route | `anthropic` / `messages` / `monitor` |
| `monitor_adaptive_supervisory_environment` | `true` (explicit) |
| `monitor_live_intervention` | `true` (key omitted; runtime and startup-guard default) |
| `monitor_ase_meta_regulation` | `false` (explicit) |
| `monitor_semantic_continuity` | `true` (key omitted; `MonitorAgent` default) |
| `context_win` | `200000` |
| `monitor_history_char_limit` | `700000` (key omitted; provider default `context_win * 3.5`) |
| provider history compaction target | `574000` characters (`0.82 * history_char_limit`) |
| `thinking_type` / `reasoning_effort` | `adaptive` / `high` |
| `max_tokens` / `temperature` | `8192` / `1` |
| `max_retries` / connect timeout / read timeout | `8` / `30` seconds / `300` seconds |

The old candidate switches required to be off by `MonitorAgent` are all false in this source profile; root scope and research view/intent are `off`. An offline construction using `load_profile`, `MonitorProviderClient`, a temporary `MonitorWorkspace`, and the `0a34cd6` `MonitorAgent` returned `ase_v0=True`, a non-null `control_echo`, and effective live intervention `True`. It made no provider request. Thus the Curator-Supervisor constructor and startup live-intervention guard pass for these profile bytes, conditional on correctly deploying them.

## Fyne Task and runner parameters

The frozen ASE-v1-core Fyne plan/manifest is used only to identify the contemporaneous Fyne gate parameters; it is not being executed or reused as a candidate run slot.

| Field | Frozen value |
| --- | --- |
| Task | `roadmapbench:fyn-2.2.0-roadmap` |
| Task profile (`GA_LLM_CONFIG_NAME`) | `native_claude_cc_vibe_opus48` |
| Task model | `claude-opus-4-8` (deployed `mykey.json` profile, not a new provider observation) |
| Task profile source | `E:\ase_v1_core_private_20261006\bundle_ASE\source\mykey.json`; SHA-256 `c3462b8d06113b5398ecb7aa6f8d22dd19584f834c3336426457ab0f29069764` |
| Task model index | `llm_no=0` |
| `GA_MAX_TURNS` | `300` |
| shared `max_agent_seconds` | `10000` |
| isolation | `no-network-unix-inference-v1` |
| frozen plan `execution_harness_sha256` / `GA_EXPERIMENT_HARNESS_SHA256` | `1c2256113d5fc8ab43e307a9edf29b16c6defeb1d5f5e69d954784cea1618bd6` |

Source locators: `GenericAgent-main/agentmain.py` (monitor config and turn limit), `GenericAgent-main/ga_monitor_adapter.py` (profile resolution), `GenericAgent-main/monitor_agent_core/agent.py` (ASE/live guard and semantic-continuity default), `GenericAgent-main/monitor_agent_core/provider.py` (history and request defaults), `E:\LongContext\long_context_bench\scripts\isolated_run_bundle.py` (deployment rewrite), and `method_discovery/runs/ase_v1_core_20261006/discovery_01/{PLAN.json,RUNNER_MANIFEST.json}` (Fyne runner parameters). The current worktree has not produced a new harness or bundle identity for a Curator Fyne run.
