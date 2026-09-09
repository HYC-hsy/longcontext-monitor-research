from __future__ import annotations

import asyncio
import importlib.util
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_harbor_tb2_m4", ROOT / "scripts" / "run_harbor_tb2_m4.py"
)
assert SPEC and SPEC.loader
m4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m4)


@pytest.mark.parametrize('config', ['', 'native_claude_cc_vibe_opus48'])
def test_model_preflight_forwards_named_config(monkeypatch, config):
    monkeypatch.setenv('GA_LLM_CONFIG_NAME', config)
    monkeypatch.setattr(m4, 'python_home', lambda: Path('python-test'))
    commands = []

    def checked(argv, timeout):
        commands.append(argv)
        return 'M4_IDENTITY={"model":"probe"}'

    monkeypatch.setattr(m4, 'checked', checked)
    assert m4.resolve_model(0)['model'] == 'probe'
    assert f'GA_LLM_CONFIG_NAME={config}' in commands[0]


def _load_adapter(monkeypatch):
    class StubBaseAgent:
        def __init__(self, logs_dir, model_name=None, extra_env=None, **kwargs):
            self.logs_dir = logs_dir
            self.model_name = model_name
            self._extra_env = extra_env or {}

        @property
        def extra_env(self):
            return dict(self._extra_env)

    modules = {
        "harbor": types.ModuleType("harbor"),
        "harbor.agents": types.ModuleType("harbor.agents"),
        "harbor.agents.base": types.ModuleType("harbor.agents.base"),
        "harbor.environments": types.ModuleType("harbor.environments"),
        "harbor.environments.base": types.ModuleType("harbor.environments.base"),
        "harbor.models": types.ModuleType("harbor.models"),
        "harbor.models.agent": types.ModuleType("harbor.models.agent"),
        "harbor.models.agent.context": types.ModuleType("harbor.models.agent.context"),
    }
    modules["harbor.agents.base"].BaseAgent = StubBaseAgent
    modules["harbor.environments.base"].BaseEnvironment = object
    modules["harbor.models.agent.context"].AgentContext = object
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location(
        "harbor_ga_agent_test", ROOT / "adapters" / "harbor_ga_agent.py"
    )
    assert spec and spec.loader
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    return adapter


class _Context:
    metadata = None


class _Result:
    def __init__(self, return_code=0, stdout="", stderr=""):
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class _FakeEnvironment:
    def __init__(self, wrapper_return_code, process_return_code):
        self.wrapper_return_code = wrapper_return_code
        self.process_return_code = process_return_code
        self.commands = []
        self.exec_calls = []

    async def exec(self, command, **kwargs):
        self.commands.append(command)
        self.exec_calls.append((command, kwargs))
        if command == "cat /logs/agent/agent_process_return_code.txt":
            return _Result(stdout=f"{self.process_return_code}\n")
        if "agentmain.py" in command:
            return _Result(return_code=self.wrapper_return_code)
        return _Result()


def _span(run_id: str, trace_id: str, model: str) -> dict:
    return {
        "traceId": trace_id,
        "attributes": [
            {"key": "benchmark.run.id", "value": {"stringValue": run_id}},
            {"key": "gen_ai.request.model", "value": {"stringValue": model}},
        ],
    }


def test_archive_trace_filters_other_runs_and_records_model(tmp_path, monkeypatch):
    otel = tmp_path / "otel"
    otel.mkdir()
    payload = {
        "resourceSpans": [{
            "resource": {},
            "scopeSpans": [{"scope": {}, "spans": [
                _span("wanted", "abc123", "Model-X"),
                _span("other", "different", "wrong-model"),
            ]}],
        }]
    }
    (otel / "traces.jsonl").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(m4, "OTEL_ROOT", otel)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    identity = m4.archive_trace("wanted", run_dir)

    assert identity["trace_id"] == "abc123"
    assert identity["trace_ids"] == ["abc123"]
    assert identity["trace_count"] == 1
    assert identity["span_count"] == 1
    assert identity["observed_models"] == ["model-x"]
    archived = (run_dir / "raw_trace.jsonl").read_text(encoding="utf-8")
    assert "wanted" in archived
    assert "other" not in archived


def test_archive_trace_accepts_multiple_traces_for_one_run(tmp_path, monkeypatch):
    otel = tmp_path / "otel"
    otel.mkdir()
    payload = {
        "resourceSpans": [{
            "resource": {},
            "scopeSpans": [{"scope": {}, "spans": [
                _span("wanted", "task-trace", "Claude-Task"),
                _span("wanted", "monitor-trace", "GPT-Monitor"),
                _span("other", "foreign-trace", "wrong-model"),
            ]}],
        }]
    }
    (otel / "traces.jsonl").write_text(json.dumps(payload) + "\n", encoding="utf-8")
    monkeypatch.setattr(m4, "OTEL_ROOT", otel)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    identity = m4.archive_trace("wanted", run_dir)

    assert identity["trace_id"] is None
    assert identity["trace_ids"] == ["monitor-trace", "task-trace"]
    assert identity["trace_count"] == 2
    assert identity["span_count"] == 2
    assert identity["observed_models"] == ["claude-task", "gpt-monitor"]
    archived = (run_dir / "raw_trace.jsonl").read_text(encoding="utf-8")
    assert "foreign-trace" not in archived


def test_archive_trace_rejects_missing_trace(tmp_path, monkeypatch):
    otel = tmp_path / "otel"
    otel.mkdir()
    (otel / "traces.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(m4, "OTEL_ROOT", otel)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(RuntimeError, match="spans=0"):
        m4.archive_trace("missing", run_dir)


def test_start_collector_reuses_only_matching_output_root(tmp_path, monkeypatch):
    monkeypatch.setattr(m4, "OTEL_ROOT", tmp_path / "current" / "otel")
    monkeypatch.setattr(m4, "collector_ready", lambda: True)
    monkeypatch.setattr(m4, "collector_matches_output", lambda: True)
    commands = []
    monkeypatch.setattr(m4, "run", lambda command, *args, **kwargs: commands.append(command))

    m4.start_collector()

    assert commands == []


def test_start_collector_replaces_ready_collector_with_stale_output(tmp_path, monkeypatch):
    monkeypatch.setattr(m4, "OTEL_ROOT", tmp_path / "current" / "otel")
    monkeypatch.setattr(m4, "collector_ready", lambda: True)
    monkeypatch.setattr(m4, "collector_matches_output", lambda: False)
    run_commands = []
    checked_commands = []

    def fake_run(command, *args, **kwargs):
        run_commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_checked(command, *args, **kwargs):
        checked_commands.append(command)
        return ""

    monkeypatch.setattr(m4, "run", fake_run)
    monkeypatch.setattr(m4, "checked", fake_checked)

    m4.start_collector()

    assert ["docker", "rm", "-f", m4.COLLECTOR_NAME] in checked_commands
    launch = next(command for command in checked_commands if command[:2] == ["docker", "run"])
    label = launch[launch.index("--label") + 1]
    assert label == f"{m4.COLLECTOR_OUTPUT_LABEL}={m4.collector_output_identity()}"
    assert str(m4.OTEL_ROOT.resolve()) in " ".join(launch)


def test_ga_hash_includes_behavior_assets_and_initial_memory(tmp_path):
    (tmp_path / "agentmain.py").write_text("print('agent')", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    prompt = tmp_path / "assets" / "sys_prompt_en.txt"
    prompt.write_text("prompt-v1", encoding="utf-8")
    (tmp_path / "memory").mkdir()
    memory = tmp_path / "memory" / "profile.txt"
    memory.write_text("memory-v1", encoding="utf-8")
    (tmp_path / "temp").mkdir()
    transient = tmp_path / "temp" / "output.txt"
    transient.write_text("run-1", encoding="utf-8")

    baseline = m4.tree_hash(tmp_path, ga_mode=True)
    prompt.write_text("prompt-v2", encoding="utf-8")
    assert m4.tree_hash(tmp_path, ga_mode=True) != baseline
    prompt.write_text("prompt-v1", encoding="utf-8")
    assert m4.tree_hash(tmp_path, ga_mode=True) == baseline
    memory.write_text("memory-v2", encoding="utf-8")
    assert m4.tree_hash(tmp_path, ga_mode=True) != baseline
    memory.write_text("memory-v1", encoding="utf-8")
    transient.write_text("run-2", encoding="utf-8")
    assert m4.tree_hash(tmp_path, ga_mode=True) == baseline


def test_harbor_ga_command_uses_read_only_mounts_and_no_solution(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    ga = tmp_path / "ga"
    runtime = tmp_path / "runtime"
    task = tmp_path / "task"
    for path in (ga, runtime, task):
        path.mkdir()
    seen = {}

    def fake_run(command, timeout=600, cwd=None):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(m4, "JOBS_ROOT", jobs)
    monkeypatch.setattr(m4, "GA_ROOT", ga)
    monkeypatch.setattr(m4, "GA_RUNTIME", runtime)
    monkeypatch.setattr(m4, "TASK_ROOT", task)
    monkeypatch.setattr(m4, "HARBOR_EXE", tmp_path / "harbor.exe")
    monkeypatch.setattr(m4, "run", fake_run)
    monkeypatch.setattr(m4, "image_identity", lambda: {})
    identity = {
        "model": {"model": "model-x", "effective_llm_no": 3},
        "runtime": {"python_home": "cpython-test"},
        "generic_agent": {"source_sha256": "source-hash"},
    }
    monkeypatch.setenv("GA_M0_MONITOR_ENABLED", "1")
    monkeypatch.setenv("GA_M0_MONITOR_CONFIG", "native_oai_cc_vibe_gpt56_sol_high")

    m4.harbor_job(
        "run-1",
        "adapters.harbor_ga_agent:M4GenericAgent",
        identity,
        agent_timeout_multiplier=2.0,
    )

    command = seen["command"]
    mounts = json.loads(command[command.index("--mounts") + 1])
    assert {item["target"] for item in mounts} == {
        "/opt/m4-runtime", "/opt/genericagent-source"
    }
    assert all(item["read_only"] is True for item in mounts)
    assert "/solution" not in " ".join(command)
    assert "llm_no=3" in command
    assert "expected_model=model-x" in command
    assert "task_id=tb2:fix-code-vulnerability" in command
    assert command[command.index("--agent-timeout-multiplier") + 1] == "2.0"
    assert "m0_monitor_enabled=True" in command


def test_harbor_job_rejects_nonpositive_agent_timeout_multiplier(tmp_path, monkeypatch):
    monkeypatch.setattr(m4, "JOBS_ROOT", tmp_path / "jobs")
    with pytest.raises(ValueError, match="must be positive"):
        m4.harbor_job("run-1", "nop", agent_timeout_multiplier=0)


@pytest.mark.parametrize(("metadata", "message"), [
    ({"run_id": "obsolete-run", "expected_model": "model-x",
      "round_end_seen": True, "wrapper_return_code": 0,
      "ga_process_return_code": 143}, "run ID"),
    ({"run_id": "job-1", "expected_model": "model-x",
      "round_end_seen": False, "wrapper_return_code": 125,
      "ga_process_return_code": 0}, "round-end"),
])
def test_finalize_rejects_invalid_agent_protocol(tmp_path, monkeypatch, metadata, message):
    jobs = tmp_path / "jobs"
    runs = tmp_path / "runs"
    trial = jobs / "job-1" / "trial-1"
    trial.mkdir(parents=True)
    result = {
        "id": "trial-id",
        "trial_name": "trial-1",
        "config": {"job_id": "job-id"},
        "agent_result": {"metadata": metadata},
        "verifier_result": {"rewards": {"reward": 0.0}},
        "exception_info": None,
    }
    (trial / "result.json").write_text(json.dumps(result), encoding="utf-8")
    monkeypatch.setattr(m4, "JOBS_ROOT", jobs)
    monkeypatch.setattr(m4, "RUNS_ROOT", runs)
    monkeypatch.setattr(m4, "archive_trace", lambda *_: {
        "trace_id": "trace", "span_count": 1,
        "observed_models": ["model-x"], "sha256": "hash",
    })
    identity = {"model": {"model": "model-x"}}

    with pytest.raises(RuntimeError, match=message):
        m4.finalize_ga("job-1", identity)
    manifest = json.loads((runs / "job-1" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["valid"] is False


def test_adapter_source_stays_thin_and_uses_native_harbor_contract():
    source = (ROOT / "adapters" / "harbor_ga_agent.py").read_text(encoding="utf-8")
    assert "class M4GenericAgent(BaseAgent)" in source
    assert "environment.exec" in source
    assert "/solution" not in source
    assert 'exit 125' in source
    assert 'if [ "$found" -eq 1 ]; then exit 0' in source
    assert "grep -Fxq" in source
    assert "grep -Fq" not in source
    assert '"wrapper_return_code"' in source
    assert '"ga_process_return_code"' in source
    assert '"agent_return_code"' not in source
    assert len(source.splitlines()) < 525


@pytest.mark.parametrize("policy", [
    "K5M2", "I0", "I1", "I2",
    "A0_ATOMIC", "A1_PRIORITY", "A2_RESIDUAL", "A3_PRIORITY_RESIDUAL",
])
def test_adapter_accepts_completion_branch_policies(monkeypatch, tmp_path, policy):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-1",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", completion_branch_checkpoint="/checkpoint",
        completion_branch_bundle="/bundle", completion_branch_policy=policy,
    )
    assert agent.completion_branch_policy == policy


def test_adapter_records_wrapper_and_real_process_status(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-1",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", task_id="tb2:test-task", timeout_sec=2,
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=143)
    context = _Context()

    asyncio.run(agent.run("instruction", environment, context))

    assert context.metadata["round_end_seen"] is True
    assert context.metadata["task_id"] == "tb2:test-task"
    assert context.metadata["wrapper_return_code"] == 0
    assert context.metadata["ga_process_return_code"] == 143


def test_adapter_forwards_clean_monitor_environment(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="clean-monitor",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", task_id="tb2:test-task", timeout_sec=2,
        monitor_enabled=True,
        monitor_config="native_oai_cc_vibe_gpt56_sol_high",
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)

    asyncio.run(agent.run("instruction", environment, _Context()))

    env = next(kwargs["env"] for command, kwargs in environment.exec_calls
               if "agentmain.py" in command)
    assert env["GA_MONITOR_ENABLED"] == "1"
    assert env["GA_MONITOR_CONFIG"] == "native_oai_cc_vibe_gpt56_sol_high"
    assert env["GA_MONITOR_ARTIFACT_DIR"] == "/logs/agent/monitor"
    assert "GA_M0_MONITOR_ENABLED" not in env
    command = next(command for command, _ in environment.exec_calls if "agentmain.py" in command)
    assert "export GA_MONITOR_RUN_DEADLINE_EPOCH=$(( $(date +%s) + 2 ))" in command
    assert command.index('completion_incomplete.json') < command.index('if [ "$found" -eq 1 ]; then exit 0; fi')


def test_clean_monitor_unfinished_review_is_not_successful_archive(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name='model-x', run_id='incomplete',
        expected_model='model-x', python_home='cpython-test', ga_source_sha256='hash',
        timeout_sec=2, monitor_enabled=True, monitor_config='fixture',
    )
    environment = _FakeEnvironment(wrapper_return_code=126, process_return_code=0)
    context = _Context()
    with pytest.raises(RuntimeError, match='did not complete'):
        asyncio.run(agent.run('instruction', environment, context))
    assert context.metadata['archive_status'] == 'monitor_review_incomplete'
    assert context.metadata['round_end_seen'] is False


def test_adapter_setup_excludes_transient_checkout_directories(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-setup",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash",
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)

    asyncio.run(agent.setup(environment))

    setup_command = environment.commands[-1]
    assert "find /opt/genericagent-source -mindepth 1 -maxdepth 1" in setup_command
    assert "! -name temp" in setup_command
    assert "! -name __pycache__" in setup_command
    assert "! -name .pytest_cache" in setup_command
    assert "cp -a /opt/genericagent-source/." not in setup_command
    assert "mkdir -p /opt/genericagent/temp" in setup_command


def test_adapter_chunks_long_instruction_before_container_exec(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-long",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2,
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=143)
    context = _Context()

    asyncio.run(agent.run("x" * 100_000, environment, context))

    chunk_commands = [command for command in environment.commands if ">>" in command]
    assert len(chunk_commands) > 20
    assert max(map(len, environment.commands)) < 5_000


def test_adapter_stages_stage4_card_and_passes_explicit_environment(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    card = json.dumps({
        "schema_version": "obligation-state/1",
        "task_id": "roadmapbench:test",
        "obligations": [{"description": "Finish target"}],
    })
    encoded = __import__("base64").b64encode(card.encode()).decode()
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-stage4",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", task_id="roadmapbench:test", timeout_sec=2,
        baseline_condition="static_checklist", experiment_id="experiment-1",
        condition_id="static_checklist", llm_config_name="named-model",
        task_card_b64=encoded, max_turns=77,
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)
    context = _Context()
    asyncio.run(agent.run("instruction", environment, context))
    agent_call = next(call for call in environment.exec_calls if "agentmain.py" in call[0])
    env = agent_call[1]["env"]
    assert env["GA_BASELINE_CONDITION"] == "static_checklist"
    assert env["GA_TASK_CARD_PATH"].endswith("stage4_task_card.json")
    assert env["GA_LLM_CONFIG_NAME"] == "named-model"
    assert env["GA_MAX_TURNS"] == "77"
    assert env["GA_TASK_WORKSPACE_DIR"] == "/app"
    assert env["GA_INLINE_LONG_PROMPT"] == "1"
    assert context.metadata["experiment_id"] == "experiment-1"
    assert context.metadata["task_workspace_dir"] == "/app"
    assert context.metadata["inline_long_prompt"] is True




def test_adapter_forwards_m3b_only_on_the_m3a_parent(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="requires the M3-A"):
        adapter.M4GenericAgent(
            logs_dir=tmp_path, model_name="model-x", run_id="invalid-m3b",
            expected_model="model-x", python_home="cpython-test",
            ga_source_sha256="hash", m0_monitor_enabled=True,
            m0_monitor_config="monitor", m3_decision_value_enabled=True,
        )
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="valid-m3b",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2, m0_monitor_enabled=True,
        m0_monitor_config="monitor", m0_recent_trajectory_turns=7,
        m3_human_loop_enabled=True,
        m3_decision_value_enabled=True,
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)
    context = _Context()

    asyncio.run(agent.run("instruction", environment, context))

    agent_call = next(call for call in environment.exec_calls if "agentmain.py" in call[0])
    assert agent_call[1]["env"]["GA_M3_HUMAN_LOOP_ENABLED"] == "1"
    assert agent_call[1]["env"]["GA_M3_DECISION_VALUE_ENABLED"] == "1"


def test_adapter_forwards_m3c_as_an_independent_m3a_child(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    with pytest.raises(ValueError, match="requires the M3-A"):
        adapter.M4GenericAgent(
            logs_dir=tmp_path, model_name="model-x", run_id="invalid-m3c",
            expected_model="model-x", python_home="cpython-test",
            ga_source_sha256="hash", m0_monitor_enabled=True,
            m0_monitor_config="monitor",
            m3_discriminative_control_enabled=True,
        )
    with pytest.raises(ValueError, match="must remain independent"):
        adapter.M4GenericAgent(
            logs_dir=tmp_path, model_name="model-x", run_id="invalid-m3bc",
            expected_model="model-x", python_home="cpython-test",
            ga_source_sha256="hash", m0_monitor_enabled=True,
            m0_monitor_config="monitor", m3_human_loop_enabled=True,
            m3_decision_value_enabled=True,
            m3_discriminative_control_enabled=True,
        )
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="valid-m3c",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2, m0_monitor_enabled=True,
        m0_monitor_config="monitor", m0_recent_trajectory_turns=7,
        m3_human_loop_enabled=True, m3_discriminative_control_enabled=True,
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)
    asyncio.run(agent.run("instruction", environment, _Context()))
    agent_call = next(call for call in environment.exec_calls if "agentmain.py" in call[0])
    assert agent_call[1]["env"]["GA_M3_DISCRIMINATIVE_CONTROL_ENABLED"] == "1"
    assert "GA_M3_DECISION_VALUE_ENABLED" not in agent_call[1]["env"]
    assert agent_call[1]["env"]["GA_M0_RECENT_TRAJECTORY_TURNS"] == "7"

    d_agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="valid-m3d",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2, m0_monitor_enabled=True,
        m0_monitor_config="monitor", m3_human_loop_enabled=True,
        m3_discriminative_control_enabled=True,
        m3_combined_control_enabled=True,
    )
    d_environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)
    asyncio.run(d_agent.run("instruction", d_environment, _Context()))
    d_call = next(call for call in d_environment.exec_calls if "agentmain.py" in call[0])
    assert d_call[1]["env"]["GA_M3_DISCRIMINATIVE_CONTROL_ENABLED"] == "1"
    assert d_call[1]["env"]["GA_M3_COMBINED_CONTROL_ENABLED"] == "1"






def test_adapter_stages_stage6d_bundle_inside_task_container(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    monkeypatch.setenv("GA_COMPLETION_CHECKPOINT_ROOT", str(tmp_path / "host-checkpoints"))
    encode = lambda text: __import__("base64").b64encode(text.encode()).decode()
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-stage6d",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2,
        evidence_state_b64=encode('{"schema_version":"evidence-carrying-task-card/0"}'),
        completion_contract_b64=encode('{"schema_version":"completion-transition-contract/0"}'),
        public_task_b64=encode("public task"), evidence_frontend_config="named",
        evidence_gate_mode="lineage_shadow",
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)
    context = _Context()
    asyncio.run(agent.run("instruction", environment, context))
    agent_call = next(call for call in environment.exec_calls if "agentmain.py" in call[0])
    env = agent_call[1]["env"]
    assert env["GA_EVIDENCE_STATE_PATH"].endswith("evidence_state.json")
    assert env["GA_COMPLETION_CONTRACT_PATH"].endswith("completion_contract.json")
    assert env["GA_PUBLIC_TASK_PATH"].endswith("public_task.txt")
    assert env["GA_EVIDENCE_FRONTEND_CONFIG"] == "named"
    assert env["GA_EVIDENCE_GATE_MODE"] == "lineage_shadow"
    assert env["GA_COMPLETION_CHECKPOINT_ROOT"] == "/logs/agent/completion_checkpoints"


def test_adapter_uses_read_only_stage6d_bundle_paths(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-stage6d-mount",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2,
        evidence_bundle_dir="/opt/stage6d-bundle", evidence_frontend_config="named",
    )
    environment = _FakeEnvironment(wrapper_return_code=0, process_return_code=0)
    context = _Context()
    asyncio.run(agent.run("instruction", environment, context))
    agent_call = next(call for call in environment.exec_calls if "agentmain.py" in call[0])
    env = agent_call[1]["env"]
    assert env["GA_EVIDENCE_STATE_PATH"] == "/opt/stage6d-bundle/evidence_state.json"
    assert env["GA_PUBLIC_TASK_PATH"] == "/opt/stage6d-bundle/public_task.txt"


def test_adapter_rejects_clean_process_exit_without_round_end(monkeypatch, tmp_path):
    adapter = _load_adapter(monkeypatch)
    agent = adapter.M4GenericAgent(
        logs_dir=tmp_path, model_name="model-x", run_id="run-2",
        expected_model="model-x", python_home="cpython-test",
        ga_source_sha256="hash", timeout_sec=2,
    )
    environment = _FakeEnvironment(wrapper_return_code=125, process_return_code=0)
    context = _Context()

    with pytest.raises(RuntimeError, match="did not complete"):
        asyncio.run(agent.run("instruction", environment, context))

    assert context.metadata["round_end_seen"] is False
    assert context.metadata["wrapper_return_code"] == 125
    assert context.metadata["ga_process_return_code"] == 0


def test_subprocess_environment_exposes_custom_adapter(tmp_path, monkeypatch):
    seen = {}

    def fake_subprocess_run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(m4.subprocess, "run", fake_subprocess_run)
    m4.run(["harbor", "jobs", "start"], cwd=tmp_path)

    pythonpath = seen["env"]["PYTHONPATH"].split(m4.os.pathsep)
    assert pythonpath[0] == str(ROOT)
    assert seen["env"]["PYTHONUTF8"] == "1"
