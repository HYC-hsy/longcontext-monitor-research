# Upstream function map (no claim of live deployment)

| Upstream identity | Research adapter | Actual status |
|---|---|---|
| `MemoryEnabledTerminus2.__init__` and vendored `harbor.agents.terminus_2.Terminus2.__init__` | `episode.construct_upstream` calls the normal constructor with `DisabledActorLLM(BaseLLM)` | Imported and constructed from fixed source; actor refusal tested. No `__new__`. |
| `_run_agent_loop` reset, `_accumulate_step`, `MemoryAgentTrigger.should_trigger`, `_trigger_memory_agent` | `PMAEpisode.task_start` and `actor_step` call the same original methods at the recorded GA actor attempt | First step and one normal multi-tool step compared to a separate scripted run of unmodified `_run_agent_loop`; full edge matrix outstanding. |
| `MemoryAgent.process` phase 1/2, memory bank and original `LiteLLM` | `construct_upstream` retains original objects; offline test replaces only instance `LiteLLM.call` with fixed responses | Original two-phase process and parser executed; real model transport not tested. |
| `_get_memory_system_prompt` with `user_turn` | `before_actor_call` consumes one original pending reminder and returns it to the bridge | Original renderer tested; actual GA next-request attachment not connected. |
| `save_memory`, `visualize_memory`, `visualize_memory_trajectory` | `task_end` saves bank/trajectory; tests call both original renderers | Offline fixture passed; no live worker cleanup proof. |
| Host file transport identity/accepted receipt concept from `analysis_spool.py` and `pilot_analysis_bridge.py` | `EventClient` / `EventDispatcher` / `worker_main` form a separate four-event protocol | Unit file bridge passed, but real Docker mounts and Harbor lifecycle not wired or certified. |
| Existing GA `agent_runner_loop` and `agentmain.run` | Default-off `GA_PMA_UPSTREAM_ENABLED` branch sends public events and task_end via `pma_upstream_bridge.py` | Fake GA tool loop and default-off regression passed; actual task container not run. |
| Existing Harbor `M4GenericAgent` | `harbor_adapter.py` pins its original byte SHA and extends only four environment names in an explicitly selected research module | Import/forward tuple check passed. No run launcher or real Harbor task trial selected this module yet. |

The vendor Harbor is loaded only by the host PMA worker. Its actor/task runner is not deployed. The additive GA branch leaves the existing Task model, system, tools, retry and completion semantics unchanged when off; live equivalence of A/B initial requests remains untested.
