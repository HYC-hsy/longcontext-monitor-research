from __future__ import annotations

import asyncio
import importlib.util
import json
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
    monkeypatch.setenv("GA_PROVIDER_MAX_RETRIES", "8")
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
        m1_active_reconstruction_enabled=True,
        m2_versioned_revision_enabled=True,
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
    assert env["GA_M1_ACTIVE_RECONSTRUCTION_ENABLED"] == "1"
    assert env["GA_M2_VERSIONED_REVISION_ENABLED"] == "1"
    assert env["GA_PROVIDER_MAX_RETRIES"] == "8"


def test_m1_workspace_requires_m0_monitor(monkeypatch):
    module = load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="requires the persistent M0 monitor"):
        module.HarborLHTBGenericAgent(
            model_name="claude-opus-4-6", llm_no=0, run_id="invalid-m1",
            expected_model="claude-opus-4-6", python_home="python-home",
            ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
            m1_workspace_enabled=True,
        )


def test_m1_active_reconstruction_requires_workspace(monkeypatch):
    module = load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="active reconstruction requires"):
        module.HarborLHTBGenericAgent(
            model_name="claude-opus-4-6", llm_no=0, run_id="invalid-active-view",
            expected_model="claude-opus-4-6", python_home="python-home",
            ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
            m0_monitor_enabled=True, m0_monitor_config="native_openai_cc_vibe",
            m1_active_reconstruction_enabled=True,
        )


def test_m2_versioned_revision_requires_workspace(monkeypatch):
    module = load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="M2 versioned revision requires"):
        module.HarborLHTBGenericAgent(
            model_name="claude-opus-4-6", llm_no=0, run_id="invalid-m2",
            expected_model="claude-opus-4-6", python_home="python-home",
            ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
            m0_monitor_enabled=True, m0_monitor_config="native_openai_cc_vibe",
            m2_versioned_revision_enabled=True,
        )


def test_m2_justification_invalidation_is_forwarded(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = module.HarborLHTBGenericAgent(
        model_name="claude-opus-4-6", llm_no=0, run_id="m2b",
        expected_model="claude-opus-4-6", python_home="python-home",
        ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
        m0_monitor_enabled=True, m0_monitor_config="native_openai_cc_vibe",
        m1_workspace_enabled=True,
        m2_justification_invalidation_enabled=True,
    )
    assert agent._agent_env("/site-packages")[
        "GA_M2_JUSTIFICATION_INVALIDATION_ENABLED"
    ] == "1"


def test_m2_candidates_are_mutually_exclusive(monkeypatch):
    module = load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="evaluated independently"):
        module.HarborLHTBGenericAgent(
            model_name="claude-opus-4-6", llm_no=0, run_id="invalid-m2-pair",
            expected_model="claude-opus-4-6", python_home="python-home",
            ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
            m0_monitor_enabled=True, m0_monitor_config="native_openai_cc_vibe",
            m1_workspace_enabled=True, m2_versioned_revision_enabled=True,
            m2_justification_invalidation_enabled=True,
        )


def test_m2_semantic_impact_is_forwarded(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = module.HarborLHTBGenericAgent(
        model_name="claude-opus-4-6", llm_no=0, run_id="m2c",
        expected_model="claude-opus-4-6", python_home="python-home",
        ga_source_sha256="abc", timeout_sec=60, task_id="lhtb:task",
        m0_monitor_enabled=True, m0_monitor_config="native_openai_cc_vibe",
        m1_workspace_enabled=True, m2_semantic_impact_enabled=True,
    )
    assert agent._agent_env("/site-packages")["GA_M2_SEMANTIC_IMPACT_ENABLED"] == "1"


class FakeMonitorSession:
    def __init__(self):
        self.max_tokens = 0
        self.reasoning_effort = "high"
        self.calls = []

    def raw_ask(self, messages):
        self.calls.append(messages)
        return iter([json.dumps({"action": "SILENT", "notes": "remember"})])


def build_active_monitor(tmp_path, monkeypatch):
    ga_root = ROOT.parent / "GenericAgent-main"
    monkeypatch.syspath_prepend(str(ga_root))
    import m0_deliberative_monitor as monitor_module
    session = FakeMonitorSession()
    monkeypatch.setattr(monitor_module, "resolve_session", lambda _: session)
    monitor = monitor_module.M0DeliberativeMonitor(
        public_task="Keep API compatibility and implement seven explicit targets.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "active",
        m1_workspace_enabled=True,
        active_reconstruction_enabled=True,
    )
    return monitor, session


def monitor_packet(turn, payload=""):
    return {
        "boundary": "turn", "internal_turn": turn,
        "response_content": f"agent intent at {turn} {payload}",
        "tool_calls": [{"tool_name": "code_run", "args": {"script": payload}}],
        "tool_results": [f"result {turn} {payload}"],
    }


def test_active_monitor_does_not_resend_prior_boundary_prompts(tmp_path, monkeypatch):
    monitor, session = build_active_monitor(tmp_path, monkeypatch)
    monitor._ask(monitor._prompt(monitor_packet(1, "FIRST_UNIQUE_MARKER"), []))
    monitor._ask(monitor._prompt(monitor_packet(2, "SECOND_UNIQUE_MARKER"), []))
    assert len(session.calls) == 2
    assert len(session.calls[0]) == len(session.calls[1]) == 3
    second_wire = json.dumps(session.calls[1], ensure_ascii=False)
    assert "SECOND_UNIQUE_MARKER" in second_wire
    assert "FIRST_UNIQUE_MARKER" not in second_wire
    assert len(monitor.history) == 2


def test_active_monitor_indexes_and_retrieves_removed_detail(tmp_path, monkeypatch):
    monitor, _ = build_active_monitor(tmp_path, monkeypatch)
    monitor._observe_boundary(monitor_packet(1, "trajectory needle"))
    monitor.semantic_workspace.apply_delta({
        "upsert": [{
            "id": "intent:one", "role": "local_intent",
            "summary": "Inspect the changed test before production edits.",
            "state": "active", "source_anchors": ["public_trajectory:turn:1"],
            "root_links": ["root:public-task"],
        }], "deactivate": [], "relations": [],
    }, turn=1, decision_index=1)
    prompt = monitor._prompt(monitor_packet(2), [])
    assert '"semantic_workspace_index"' in prompt
    assert '"m1_semantic_workspace"' not in prompt
    assert '"durable_monitor_checkpoint"' not in prompt
    original = monitor._inspect_trajectory({"operation": "read_original_task"})
    recent = monitor._inspect_trajectory({"operation": "read_recent_delta", "limit": 1})
    semantic = monitor._inspect_semantic_workspace({
        "operation": "read_semantic_object", "id": "intent:one",
    })
    assert original["ok"] and "seven explicit targets" in original["public_task"]
    assert recent["ok"] and "trajectory needle" in json.dumps(recent)
    assert semantic["ok"] and semantic["object"]["id"] == "intent:one"


def test_monitor_raises_bounded_transport_retry_floor(tmp_path, monkeypatch):
    _, session = build_active_monitor(tmp_path, monkeypatch)
    assert session.max_retries == 4


@pytest.mark.parametrize("status,body", [
    (400, '{"error":{"type":"upstream_error","message":"temporary"}}'),
    (400, '{"error":{"message":"Upstream request failed"}}'),
    (429, '{"code":"DAILY_LIMIT_EXCEEDED"}'),
    (503, "temporarily unavailable"),
])
def test_retryable_provider_failures(status, body, monkeypatch):
    ga_root = ROOT.parent / "GenericAgent-main"
    monkeypatch.syspath_prepend(str(ga_root))
    from llmcore import _retryable_http_error
    assert _retryable_http_error(status, body)


@pytest.mark.parametrize("status,body", [
    (400, '{"error":{"type":"invalid_request_error"}}'),
    (400, '{"error":{"message":"unsupported parameter"}}'),
    (401, '{"error":{"type":"authentication_error"}}'),
    (403, '{"error":{"type":"permission_error"}}'),
    (404, "not found"),
])
def test_permanent_provider_failures_are_not_retried(status, body, monkeypatch):
    ga_root = ROOT.parent / "GenericAgent-main"
    monkeypatch.syspath_prepend(str(ga_root))
    from llmcore import _retryable_http_error
    assert not _retryable_http_error(status, body)


class FakeHTTPResponse:
    def __init__(self, status_code, text=""):
        self.status_code = status_code
        self.text = text
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def stream_session():
    return SimpleNamespace(
        max_retries=4, stream=False, connect_timeout=1, read_timeout=1,
        proxies=None, verify=True,
    )


def successful_parse(_response):
    yield "ok"
    return [{"type": "text", "text": "ok"}]


def test_relay_wrapped_upstream_400_retries_through_success(monkeypatch):
    ga_root = ROOT.parent / "GenericAgent-main"
    monkeypatch.syspath_prepend(str(ga_root))
    import llmcore
    responses = iter([
        FakeHTTPResponse(400, '{"error":{"type":"upstream_error"}}'),
        FakeHTTPResponse(200),
    ])
    calls = []
    monkeypatch.setattr(llmcore.requests, "post", lambda *a, **k: (calls.append(1), next(responses))[1])
    monkeypatch.setattr(llmcore.time, "sleep", lambda seconds: None)

    chunks = list(llmcore._stream_with_retry(
        stream_session(), "https://relay.invalid/v1/responses", {}, {}, successful_parse,
    ))

    assert chunks == ["ok"]
    assert len(calls) == 2


def test_invalid_request_400_does_not_retry(monkeypatch):
    ga_root = ROOT.parent / "GenericAgent-main"
    monkeypatch.syspath_prepend(str(ga_root))
    import llmcore
    calls = []
    monkeypatch.setattr(
        llmcore.requests, "post",
        lambda *a, **k: (
            calls.append(1),
            FakeHTTPResponse(400, '{"error":{"type":"invalid_request_error"}}'),
        )[1],
    )

    chunks = list(llmcore._stream_with_retry(
        stream_session(), "https://relay.invalid/v1/responses", {}, {}, successful_parse,
    ))

    assert len(calls) == 1
    assert chunks and chunks[0].startswith("!!!Error: HTTP 400")


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


def test_round_end_requires_an_exact_protocol_line(monkeypatch):
    module = load_adapter(monkeypatch)
    agent = make_agent(module)
    environment = FakeEnvironment([0])
    context = StubContext()

    asyncio.run(agent.run("instruction", environment, context))

    wait = next(command for command, _ in environment.calls
                if "for i in $(seq" in command)
    assert "grep -Fxq" in wait
    assert "grep -Fq" not in wait


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
