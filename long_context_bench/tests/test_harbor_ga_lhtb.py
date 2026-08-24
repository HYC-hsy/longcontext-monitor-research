from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]


class StubBaseAgent:
    def __init__(self, *args, model_name=None, **kwargs):
        self.model_name = model_name


class StubContext:
    metadata = None


def load_adapter(monkeypatch):
    modules = {
        "harbor": types.ModuleType("harbor"),
        "harbor.agents": types.ModuleType("harbor.agents"),
        "harbor.agents.base": types.ModuleType("harbor.agents.base"),
        "harbor.environments": types.ModuleType("harbor.environments"),
        "harbor.environments.base": types.ModuleType("harbor.environments.base"),
        "harbor.models": types.ModuleType("harbor.models"),
        "harbor.models.agent": types.ModuleType("harbor.models.agent"),
        "harbor.models.agent.context": types.ModuleType(
            "harbor.models.agent.context"
        ),
    }
    modules["harbor.agents.base"].BaseAgent = StubBaseAgent
    modules["harbor.environments.base"].BaseEnvironment = object
    modules["harbor.models.agent.context"].AgentContext = StubContext
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    for name in ("adapters.harbor_ga_agent", "adapters.harbor_ga_lhtb"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    spec = importlib.util.spec_from_file_location(
        "adapters.harbor_ga_lhtb", ROOT / "adapters" / "harbor_ga_lhtb.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["adapters.harbor_ga_lhtb"] = module
    spec.loader.exec_module(module)
    return module


class FakeEnvironment:
    def __init__(self, wait_codes):
        self.wait_codes = iter(wait_codes)
        self.calls = []

    async def exec(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if "for i in $(seq" in command:
            return SimpleNamespace(
                return_code=next(self.wait_codes), stdout="", stderr=""
            )
        if command.startswith("cat "):
            return SimpleNamespace(return_code=0, stdout="", stderr="")
        return SimpleNamespace(return_code=0, stdout="", stderr="")


def make_agent(module):
    return module.HarborLHTBGenericAgent(
        model_name="claude-opus-4-6",
        llm_no=0,
        run_id="m12:lhtb/task",
        expected_model="claude-opus-4-6",
        python_home="python-home",
        ga_source_sha256="abc",
        timeout_sec=60,
        task_id="lhtb:task",
    )


def test_first_phase_starts_persistent_process(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = make_agent(module)
    environment = FakeEnvironment([0])
    context = StubContext()

    asyncio.run(agent.run("initial task", environment, context))

    stage = next(command for command, _ in environment.calls if "agentmain.py" in command)
    wait = next(command for command, _ in environment.calls if "for i in $(seq" in command)
    assert "agentmain.py" in stage
    assert "agent.pid" in stage
    assert "&& { ( " in stage
    assert "agent.pid; }" in stage
    assert (
        next(kwargs for command, kwargs in environment.calls if "agentmain.py" in command)["env"]["GA_BENCH_EXPECTED_TURNS"]
        == "1000000"
    )
    assert "kill " not in wait
    assert "output.txt" in wait
    assert context.metadata["persistent_session"] is True
    assert context.metadata["continuation_phase"] == 0
    assert agent._phase == 1


def test_lhtb_forwards_research_and_manual_completion_environment(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = module.HarborLHTBGenericAgent(
        model_name="claude-opus-4-6",
        llm_no=0,
        run_id="human-loop",
        expected_model="claude-opus-4-6",
        python_home="python-home",
        ga_source_sha256="abc",
        timeout_sec=60,
        task_id="lhtb:task",
        experiment_id="exp-1",
        condition_id="human_monitor",
        llm_config_name="native_claude_cc_vibe",
        max_turns=500,
        manual_completion_dir="/logs/agent/manual_completion",
        manual_completion_timeout_seconds=3600,
        m0_monitor_enabled=True,
        m0_monitor_config="native_openai_cc_vibe",
        m0_max_inspections=12,
        m1_workspace_enabled=True,
    )

    env = agent._agent_env("/site-packages")

    assert env["GA_MAX_TURNS"] == "500"
    assert env["GA_RESEARCH_EVENT_PATH"] == "/logs/agent/research_events.jsonl"
    assert env["GA_EXPERIMENT_ID"] == "exp-1"
    assert env["GA_CONDITION_ID"] == "human_monitor"
    assert env["GA_LLM_CONFIG_NAME"] == "native_claude_cc_vibe"
    assert env["GA_MANUAL_COMPLETION_DIR"] == "/logs/agent/manual_completion"
    assert env["GA_MANUAL_COMPLETION_TIMEOUT_SECONDS"] == "3600.0"
    assert env["GA_M0_MONITOR_ENABLED"] == "1"
    assert env["GA_M0_MONITOR_CONFIG"] == "native_openai_cc_vibe"
    assert env["GA_M0_MAX_INSPECTIONS"] == "12"
    assert env["GA_M0_MONITOR_ARTIFACT_DIR"] == "/logs/agent/m0_monitor"
    assert env["GA_M1_WORKSPACE_ENABLED"] == "1"


def test_m1_workspace_requires_m0_monitor(monkeypatch):
    module = load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="requires the persistent M0 monitor"):
        module.HarborLHTBGenericAgent(
            model_name="claude-opus-4-6", llm_no=0, run_id="invalid-m1",
            expected_model="claude-opus-4-6", python_home="python-home",
            ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
            m1_workspace_enabled=True,
        )


def test_second_phase_uses_reply_without_restarting(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = make_agent(module)
    agent._phase = 1
    environment = FakeEnvironment([0])
    context = StubContext()

    asyncio.run(agent.run("verifier feedback", environment, context))

    commands = [command for command, _ in environment.calls]
    wait = next(command for command in commands if "for i in $(seq" in command)
    assert any("reply.txt.b64" in command for command in commands)
    assert not any("agentmain.py" in command for command in commands)
    assert "output1.txt" in wait
    assert context.metadata["continuation_phase"] == 1
    assert agent._phase == 2


def test_long_instruction_is_chunked_before_container_exec(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = make_agent(module)
    environment = FakeEnvironment([0])
    context = StubContext()

    asyncio.run(agent.run("x" * 100_000, environment, context))

    commands = [command for command, _ in environment.calls]
    append_commands = [command for command in commands if ">>" in command]
    assert len(append_commands) > 20
    assert max(map(len, commands)) < 5000


def test_missing_round_end_fails_without_advancing_phase(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = make_agent(module)
    environment = FakeEnvironment([125])
    context = StubContext()

    with pytest.raises(RuntimeError, match="did not complete continuation phase 0"):
        asyncio.run(agent.run("initial task", environment, context))

    assert context.metadata["round_end_seen"] is False
    assert context.metadata["wrapper_return_code"] == 125
    assert agent._phase == 0
