"""Harbor adapter that runs one isolated GenericAgent task-mode turn."""

from __future__ import annotations
import base64
import json
import os
import posixpath
import shlex
from pathlib import Path
from adapters.failure_snapshot import preserve_failed_workspace
from adapters.isolated_setup import start_isolated_transport, ENVIRONMENT_NOTE

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


CONTAINER_RUNTIME = "/opt/m4-runtime"
CONTAINER_SOURCE = "/opt/genericagent-source"
CONTAINER_GA = "/opt/genericagent"
ROUND_END = "[ROUND END]"
FORWARDED_ENV_VARS = (
    "GA_PMA_ENABLED", "GA_PMA_CONFIG", "GA_PMA_ARTIFACT_DIR",
    "GA_RUN_ISOLATION",
    "GA_MONITOR_GROUNDED_CONTEXT",
    "GA_MONITOR_HANDOFF_VALIDATION",
    "GA_MONITOR_ADVICE_REVISION",
    "GA_MONITOR_FEEDBACK_FOCUS",
    "GA_MONITOR_INQUIRY",
    "GA_MONITOR_TOOL_FEEDBACK",
    "GA_MONITOR_ACTIVE_WORKING_CONTEXT",
    "GA_PROVIDER_MAX_RETRIES",
    "GA_MONITOR_REQUEST_TIMEOUT_SECONDS",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "DASHSCOPE_API_KEY",
    "INFINI_API_KEY",
)


def _q(value: object) -> str:
    return shlex.quote(str(value))


def _runtime_paths(python_home: str) -> tuple[str, str]:
    base = f"{CONTAINER_RUNTIME}/python/{python_home}"
    return f"{base}/bin/python3.12", f"{CONTAINER_RUNTIME}/ga-env/lib/python3.12/site-packages"


class M4GenericAgent(BaseAgent):
    """Thin bridge: Harbor owns the environment; GA owns the tool loop."""

    def __init__(
        self,
        *args,
        llm_no: int | str = 0,
        run_id: str,
        expected_model: str,
        python_home: str,
        ga_source_sha256: str,
        task_id: str = "tb2:fix-code-vulnerability",
        collector_endpoint: str = "http://host.docker.internal:14319/v1/traces",
        timeout_sec: int | str = 900,
        telemetry_service_name: str = "genericagent-harbor-tb2",
        metadata_schema_version: str = "harbor-ga-m4-agent/2",
        baseline_condition: str = "original",
        experiment_id: str = "",
        condition_id: str = "",
        llm_config_name: str = "",
        task_card_b64: str = "",
        obligation_ledger_card_b64: str = "",
        evidence_state_b64: str = "",
        completion_contract_b64: str = "",
        public_task_b64: str = "",
        evidence_frontend_config: str = "",
        evidence_gate_mode: str = "",
        evidence_bundle_dir: str = "",
        completion_branch_checkpoint: str = "",
        completion_branch_bundle: str = "",
        completion_branch_policy: str = "",
        manual_completion_dir: str = "",
        manual_completion_timeout_seconds: float | str = 300,
        monitor_enabled: bool | str = False,
        monitor_config: str = "",
        m0_monitor_enabled: bool | str = False,
        m0_monitor_config: str = "",
        m0_max_inspections: int | str = 8,
        m0_recent_trajectory_turns: int | str = 0,
        m3_human_loop_enabled: bool | str = False,
        m3_decision_value_enabled: bool | str = False,
        m3_discriminative_control_enabled: bool | str = False,
        m3_combined_control_enabled: bool | str = False,
        max_turns: int | str = 180,
        task_workspace_dir: str = "/app",
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.llm_no = int(llm_no)
        self.run_id = run_id
        self.expected_model = expected_model.lower()
        self.python_home = python_home
        self.ga_source_sha256 = ga_source_sha256
        self.task_id = task_id
        self.collector_endpoint = collector_endpoint
        self.timeout_sec = int(timeout_sec)
        self.telemetry_service_name = telemetry_service_name
        self.metadata_schema_version = metadata_schema_version
        self.baseline_condition = baseline_condition
        self.experiment_id = experiment_id
        self.condition_id = condition_id or baseline_condition
        self.llm_config_name = llm_config_name
        self.task_card_b64 = task_card_b64
        self.obligation_ledger_card_b64 = obligation_ledger_card_b64
        self.evidence_state_b64 = evidence_state_b64
        self.completion_contract_b64 = completion_contract_b64
        self.public_task_b64 = public_task_b64
        self.evidence_frontend_config = evidence_frontend_config
        if evidence_gate_mode not in {"", "lineage_shadow", "hierarchical_active"}:
            raise ValueError("unsupported evidence_gate_mode")
        self.evidence_gate_mode = evidence_gate_mode
        self.evidence_bundle_dir = evidence_bundle_dir
        if len({bool(completion_branch_checkpoint), bool(completion_branch_bundle),
                bool(completion_branch_policy)}) != 1:
            raise ValueError("completion branch checkpoint, bundle, and policy must be provided together")
        supported_branch_policies = {
            "K4", "K5", "K5M2", "I0", "I1", "I2",
            "A0_ATOMIC", "A1_PRIORITY", "A2_RESIDUAL",
            "A3_PRIORITY_RESIDUAL",
        }
        if (completion_branch_policy
                and completion_branch_policy not in supported_branch_policies):
            raise ValueError("unsupported completion branch policy")
        self.completion_branch_checkpoint = completion_branch_checkpoint
        self.completion_branch_bundle = completion_branch_bundle
        self.completion_branch_policy = completion_branch_policy
        self.manual_completion_dir = manual_completion_dir
        self.manual_completion_timeout_seconds = float(manual_completion_timeout_seconds)
        self.monitor_enabled = str(monitor_enabled).lower() in {"1", "true", "yes"}
        self.monitor_config = monitor_config
        self.m0_monitor_enabled = str(m0_monitor_enabled).lower() in {"1", "true", "yes"}
        self.m0_monitor_config = m0_monitor_config
        self.m0_max_inspections = int(m0_max_inspections)
        self.m0_recent_trajectory_turns = int(m0_recent_trajectory_turns)
        self.m3_human_loop_enabled = str(
            m3_human_loop_enabled
        ).lower() in {"1", "true", "yes"}
        self.m3_decision_value_enabled = str(
            m3_decision_value_enabled
        ).lower() in {"1", "true", "yes"}
        self.m3_discriminative_control_enabled = str(
            m3_discriminative_control_enabled
        ).lower() in {"1", "true", "yes"}
        self.m3_combined_control_enabled = str(m3_combined_control_enabled).lower() in {"1", "true", "yes"}
        if self.monitor_enabled and not self.monitor_config:
            raise ValueError("Clean monitor config is required when the Monitor is enabled")
        if self.monitor_enabled and self.m0_monitor_enabled:
            raise ValueError("Clean and historical Monitor runtimes cannot be combined")
        if self.m0_monitor_enabled and not self.m0_monitor_config:
            raise ValueError("M0 monitor config is required when M0 is enabled")
        if self.m3_decision_value_enabled and not self.m3_human_loop_enabled:
            raise ValueError("M3-B requires the M3-A parent")
        if (self.m3_discriminative_control_enabled
                and not self.m3_human_loop_enabled):
            raise ValueError("M3-C requires the M3-A parent")
        if (self.m3_decision_value_enabled
                and self.m3_discriminative_control_enabled):
            raise ValueError("M3-B and M3-C must remain independent candidates")
        if (self.m3_combined_control_enabled
                and not self.m3_discriminative_control_enabled):
            raise ValueError("M3-D requires the M3-C parent")
        self.max_turns = int(max_turns)
        if not task_workspace_dir.startswith("/"):
            raise ValueError("task_workspace_dir must be an absolute container path")
        self.task_workspace_dir = task_workspace_dir
        if not self.model_name or self.model_name.lower() != self.expected_model:
            raise ValueError(
                "Harbor --model must equal the model resolved from GA llm_no: "
                f"expected {self.expected_model!r}, got {self.model_name!r}"
            )

    @staticmethod
    def name() -> str:
        return "generic-agent-m4"

    def version(self) -> str:
        return "1"

    async def _stage_text(
        self,
        environment: BaseEnvironment,
        destination: str,
        text: str,
    ) -> None:
        """Write text without placing an unbounded payload on the host CLI."""
        encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
        encoded_path = destination + ".b64"
        prepared = await environment.exec(
            f"mkdir -p {_q(posixpath.dirname(destination))} && "
            f": > {_q(encoded_path)}",
            timeout_sec=30,
            user="root",
        )
        if prepared.return_code:
            raise RuntimeError("failed to prepare staged GA text")
        for start in range(0, len(encoded), 4096):
            chunk = encoded[start : start + 4096]
            appended = await environment.exec(
                f"printf %s {_q(chunk)} >> {_q(encoded_path)}",
                timeout_sec=30,
                user="root",
            )
            if appended.return_code:
                raise RuntimeError("failed to append staged GA text")
        decoded = await environment.exec(
            f"base64 -d {_q(encoded_path)} > {_q(destination)} && "
            f"rm -f {_q(encoded_path)}",
            timeout_sec=30,
            user="root",
        )
        if decoded.return_code:
            raise RuntimeError("failed to decode staged GA text")

    async def setup(self, environment: BaseEnvironment) -> None:
        python_bin, site_packages = _runtime_paths(self.python_home)
        # The bind-mounted checkout may contain hundreds of megabytes of prior
        # run artifacts under temp/.  They are not part of the frozen source
        # identity and must not be copied into every trial container.
        copy_runtime = (
            f"find {_q(CONTAINER_SOURCE)} -mindepth 1 -maxdepth 1 "
            "! -name temp ! -name __pycache__ ! -name .pytest_cache "
            f"-exec cp -a -- {{}} {_q(CONTAINER_GA + '/')} \\;"
        )
        command = " && ".join(
            [
                f"test -x {_q(python_bin)}",
                f"test -d {_q(site_packages)}",
                f"test -f {_q(CONTAINER_SOURCE + '/agentmain.py')}",
                f"rm -rf {_q(CONTAINER_GA)}",
                f"mkdir -p {_q(CONTAINER_GA)}",
                copy_runtime,
                f"mkdir -p {_q(CONTAINER_GA + '/temp')} /logs/agent",
            ]
        )
        result = await environment.exec(command, timeout_sec=180, user="root")
        if result.return_code:
            raise RuntimeError(f"GA setup failed: {result.stderr or result.stdout}")
        if os.environ.get('GA_RUN_ISOLATION') == 'no-network-unix-inference-v1':
            await start_isolated_transport(environment, python_bin, CONTAINER_GA)

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        agent_id = self.run_id.replace(":", "_").replace("/", "_")
        task_dir = f"{CONTAINER_GA}/temp/{agent_id}"
        python_bin, site_packages = _runtime_paths(self.python_home)
        if os.environ.get('GA_RUN_ISOLATION') == 'no-network-unix-inference-v1':
            instruction += ENVIRONMENT_NOTE
        await self._stage_text(environment, task_dir + "/input.txt", instruction)
        if self.completion_branch_checkpoint:
            restored = await environment.exec(
                f"find {_q(self.task_workspace_dir)} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} + && "
                f"cp -a {_q(self.completion_branch_checkpoint + '/workspace/.')} "
                f"{_q(self.task_workspace_dir + '/')} && "
                f"cp {_q(self.completion_branch_bundle + '/resume_prompt.txt')} "
                f"{_q(task_dir + '/input.txt')}",
                timeout_sec=180, user="root",
            )
            if restored.return_code:
                raise RuntimeError("failed to restore completion branch workspace")
        task_card_path = ""
        if self.task_card_b64:
            try:
                task_card = base64.b64decode(self.task_card_b64).decode("utf-8")
                parsed_card = json.loads(task_card)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("invalid Stage 4 task_card_b64") from error
            if parsed_card.get("schema_version") != "obligation-state/1":
                raise ValueError("unsupported Stage 4 task card schema")
            task_card_path = task_dir + "/stage4_task_card.json"
            await self._stage_text(environment, task_card_path, task_card)
        ledger_card_path = ""
        if self.obligation_ledger_card_b64:
            try:
                ledger_card = base64.b64decode(
                    self.obligation_ledger_card_b64
                ).decode("utf-8")
                parsed_ledger = json.loads(ledger_card)
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ValueError("invalid obligation_ledger_card_b64") from error
            if parsed_ledger.get("schema_version") != "obligation-ledger-card/1":
                raise ValueError("unsupported obligation ledger card schema")
            ledger_card_path = task_dir + "/obligation_ledger_card.json"
            await self._stage_text(environment, ledger_card_path, ledger_card)
        evidence_paths = {}
        encoded_inputs = {
            "GA_EVIDENCE_STATE_PATH": (self.evidence_state_b64, "evidence_state.json"),
            "GA_COMPLETION_CONTRACT_PATH": (
                self.completion_contract_b64, "completion_contract.json"
            ),
            "GA_PUBLIC_TASK_PATH": (self.public_task_b64, "public_task.txt"),
        }
        if self.evidence_bundle_dir:
            if self.evidence_bundle_dir != "/opt/stage6d-bundle":
                raise ValueError("unsupported Stage 6D bundle mount")
            evidence_paths = {
                "GA_EVIDENCE_STATE_PATH": self.evidence_bundle_dir + "/evidence_state.json",
                "GA_COMPLETION_CONTRACT_PATH": (
                    self.evidence_bundle_dir + "/completion_contract.json"
                ),
                "GA_PUBLIC_TASK_PATH": self.evidence_bundle_dir + "/public_task.txt",
            }
        elif any(value[0] for value in encoded_inputs.values()):
            if not all(value[0] for value in encoded_inputs.values()):
                raise ValueError("incomplete Stage 6D runtime bundle")
            for env_name, (encoded, filename) in encoded_inputs.items():
                try:
                    text = base64.b64decode(encoded).decode("utf-8")
                except (ValueError, UnicodeDecodeError) as error:
                    raise ValueError("invalid Stage 6D runtime bundle") from error
                destination = task_dir + "/" + filename
                await self._stage_text(environment, destination, text)
                evidence_paths[env_name] = destination
        prepare = (
            f"mkdir -p /logs/agent && "
            f"rm -f {_q(task_dir + '/output.txt')} {_q(task_dir + '/reply.txt')}"
        )
        result = await environment.exec(prepare, timeout_sec=30, user="root")
        if result.return_code:
            raise RuntimeError(f"failed to stage GA instruction: {result.stderr or result.stdout}")

        env = {
            "PYTHONPATH": f"{site_packages}:{CONTAINER_GA}",
            "GA_LANG": "en",
            "GA_OTEL_ENABLED": "1",
            "GA_OTEL_CAPTURE_CONTENT": "0",
            "GA_BENCH_RUN_ID": self.run_id,
            "GA_BENCH_TASK_ID": self.task_id,
            "GA_BENCH_EXPECTED_TURNS": "1",
            "GA_OTEL_ARTIFACT_DIR": "/logs/agent",
            "OTEL_SERVICE_NAME": self.telemetry_service_name,
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": self.collector_endpoint,
            "GA_BASELINE_CONDITION": self.baseline_condition,
            "GA_MAX_TURNS": str(self.max_turns),
            "GA_RESEARCH_EVENT_PATH": "/logs/agent/research_events.jsonl",
            "GA_EXPERIMENT_ID": self.experiment_id,
            "GA_CONDITION_ID": self.condition_id,
            "GA_TASK_WORKSPACE_DIR": self.task_workspace_dir,
            "GA_INLINE_LONG_PROMPT": "1",
        }
        if self.llm_config_name:
            env["GA_LLM_CONFIG_NAME"] = self.llm_config_name
        if task_card_path:
            env["GA_TASK_CARD_PATH"] = task_card_path
        if ledger_card_path:
            env["GA_OBLIGATION_LEDGER_CARD_PATH"] = ledger_card_path
        env.update(evidence_paths)
        if self.evidence_frontend_config:
            env["GA_EVIDENCE_FRONTEND_CONFIG"] = self.evidence_frontend_config
        if self.evidence_gate_mode:
            env["GA_EVIDENCE_GATE_MODE"] = self.evidence_gate_mode
        if self.completion_branch_checkpoint:
            env["GA_COMPLETION_BRANCH_CHECKPOINT"] = self.completion_branch_checkpoint
            env["GA_COMPLETION_BRANCH_BUNDLE"] = self.completion_branch_bundle
            env["GA_COMPLETION_BRANCH_POLICY"] = self.completion_branch_policy
        if self.manual_completion_dir:
            env["GA_MANUAL_COMPLETION_DIR"] = self.manual_completion_dir
            env["GA_MANUAL_COMPLETION_TIMEOUT_SECONDS"] = str(
                self.manual_completion_timeout_seconds
            )
        if self.monitor_enabled:
            env["GA_MONITOR_ENABLED"] = "1"
            env["GA_MONITOR_CONFIG"] = self.monitor_config
            env["GA_MONITOR_ARTIFACT_DIR"] = "/logs/agent/monitor"
        if self.m0_monitor_enabled:
            env["GA_M0_MONITOR_ENABLED"] = "1"
            env["GA_M0_MONITOR_CONFIG"] = self.m0_monitor_config
            env["GA_M0_MAX_INSPECTIONS"] = str(self.m0_max_inspections)
            env["GA_M0_RECENT_TRAJECTORY_TURNS"] = str(
                self.m0_recent_trajectory_turns
            )
            env["GA_M0_MONITOR_ARTIFACT_DIR"] = "/logs/agent/m0_monitor"
            feature_env = {
                "GA_M3_HUMAN_LOOP_ENABLED": self.m3_human_loop_enabled,
                "GA_M3_DECISION_VALUE_ENABLED": self.m3_decision_value_enabled,
                "GA_M3_DISCRIMINATIVE_CONTROL_ENABLED": self.m3_discriminative_control_enabled,
                "GA_M3_COMBINED_CONTROL_ENABLED": self.m3_combined_control_enabled,
            }
            env.update({name: "1" for name, enabled in feature_env.items() if enabled})
        if os.environ.get("GA_COMPLETION_CHECKPOINT_ROOT"):
            env["GA_COMPLETION_CHECKPOINT_ROOT"] = "/logs/agent/completion_checkpoints"
        for name in FORWARDED_ENV_VARS:
            if os.environ.get('GA_RUN_ISOLATION') == 'no-network-unix-inference-v1' and name.endswith('_API_KEY'):
                continue
            value = os.environ.get(name)
            if value:
                env[name] = value

        iterations = max(1, self.timeout_sec // 2)
        output = f"{task_dir}/output.txt"
        # Establish identity before the long await: Harbor can cancel it at its
        # outer deadline before the normal result/metadata path is reached.
        partial_metadata = {
            "schema_version": self.metadata_schema_version,
            "run_id": self.run_id, "task_id": self.task_id,
            "llm_no": self.llm_no, "expected_model": self.expected_model,
            "ga_source_sha256": self.ga_source_sha256,
            "round_end_seen": False, "wrapper_return_code": None,
            "ga_process_return_code": None, "archive_status": "running_partial",
            "experiment_id": self.experiment_id, "condition_id": self.condition_id,
            "baseline_condition": self.baseline_condition,
            "task_workspace_dir": self.task_workspace_dir,
            "inline_long_prompt": True,
        }
        context.metadata = partial_metadata
        await environment.exec(
            "printf %s "
            + _q(base64.b64encode(json.dumps(partial_metadata, sort_keys=True).encode()).decode())
            + " | base64 -d > /logs/agent/m4_agent_identity.json",
            timeout_sec=30, user="root",
        )
        command = f"""
set +e
archive_output() {{
  if [ -f {_q(output)} ]; then
    cp {_q(output)} /logs/agent/output.txt.pending && mv /logs/agent/output.txt.pending /logs/agent/output.txt
  fi
}}
trap archive_output EXIT
{('export GA_MONITOR_RUN_DEADLINE_EPOCH=$(( $(date +%s) + ' + str(iterations * 2) + ' ))') if self.monitor_enabled else ''}
{_q(python_bin)} {_q(CONTAINER_GA + '/agentmain.py')} --task {_q(agent_id)} \
  {('--history ' + _q(self.completion_branch_checkpoint + '/state/session.json')) if self.completion_branch_checkpoint else ''} \
  --llm_no {_q(self.llm_no)} --nobg --verbose --no-user-tools \
  > /logs/agent/agent_stdout.log 2> /logs/agent/agent_stderr.log &
pid=$!
found=0
timed_out=1
for i in $(seq 1 {iterations}); do
  archive_output
  if grep -Fxq {_q(ROUND_END)} {_q(output)} 2>/dev/null; then found=1; timed_out=0; break; fi
  if ! kill -0 "$pid" 2>/dev/null; then timed_out=0; break; fi
  sleep 2
done
if kill -0 "$pid" 2>/dev/null; then kill "$pid" 2>/dev/null; fi
wait "$pid" 2>/dev/null
agent_rc=$?
cp {_q(output)} /logs/agent/output.txt 2>/dev/null || true
printf '%s\n' "$agent_rc" > /logs/agent/agent_process_return_code.txt
{('if [ -f /logs/agent/monitor/completion_incomplete.json ]; then exit 126; fi') if self.monitor_enabled else ''}
if [ "$found" -eq 1 ]; then exit 0; fi
if [ "$timed_out" -eq 1 ]; then exit 124; fi
# A clean child exit is not a completed turn without the protocol sentinel.
exit 125
""".strip()
        try:
            result = await environment.exec(
                command, cwd="/app", env=env,
                timeout_sec=self.timeout_sec + 90, user="root",
            )
        except BaseException:
            # Preserve the original cancellation/transport error, even if cleanup fails.
            await preserve_failed_workspace(environment, python_bin, self.task_workspace_dir, context.metadata)
            raise
        failure_snapshot = None
        if result.return_code:
            failure_snapshot = await preserve_failed_workspace(
                environment, python_bin, self.task_workspace_dir, context.metadata)
        process_result = await environment.exec(
            "cat /logs/agent/agent_process_return_code.txt",
            timeout_sec=30,
            user="root",
        )
        try:
            process_return_code = int((process_result.stdout or "").strip())
        except ValueError:
            process_return_code = None
        metadata = {
            "schema_version": self.metadata_schema_version,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "llm_no": self.llm_no,
            "expected_model": self.expected_model,
            "ga_source_sha256": self.ga_source_sha256,
            "round_end_seen": result.return_code == 0,
            "wrapper_return_code": result.return_code,
            "ga_process_return_code": process_return_code,
            "experiment_id": self.experiment_id,
            "condition_id": self.condition_id,
            "baseline_condition": self.baseline_condition,
            "task_workspace_dir": self.task_workspace_dir,
            "inline_long_prompt": True,
            "archive_status": ("monitor_review_incomplete" if self.monitor_enabled and result.return_code == 126
                               else "finished" if result.return_code == 0 else "failed"),
        }
        if failure_snapshot is not None:
            metadata['failure_workspace_snapshot'] = failure_snapshot
        context.metadata = metadata
        await environment.exec(
            "printf %s "
            + _q(base64.b64encode(json.dumps(metadata, sort_keys=True).encode()).decode())
            + " | base64 -d > /logs/agent/m4_agent_identity.json",
            timeout_sec=30,
            user="root",
        )
        if result.return_code:
            detail = result.stderr or result.stdout or (
                f"wrapper_exit={result.return_code}, child_exit={process_return_code}; "
                "see archived output.txt, monitor/completion_incomplete.json and failure_workspace/report.json")
            raise RuntimeError(f"GenericAgent did not complete one task turn: {detail}")


class HarborGenericAgent(M4GenericAgent):
    """Benchmark-neutral name for the same Natural GenericAgent bridge."""

    @staticmethod
    def name() -> str:
        return "generic-agent-harbor-natural"


__all__ = ["HarborGenericAgent", "M4GenericAgent"]
