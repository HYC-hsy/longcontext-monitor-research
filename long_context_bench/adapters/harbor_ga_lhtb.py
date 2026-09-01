"""LHTB Harbor adapter that resumes one persistent GenericAgent session."""

from __future__ import annotations

import base64
import json

from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

from adapters.harbor_ga_agent import (
    CONTAINER_GA,
    FORWARDED_ENV_VARS,
    ROUND_END,
    HarborGenericAgent,
    _q,
    _runtime_paths,
)


class HarborLHTBGenericAgent(HarborGenericAgent):
    """Bridge Harbor continuation phases to GA's native ``reply.txt`` protocol."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault(
            "metadata_schema_version", "harbor-ga-lhtb-continuation/1"
        )
        kwargs.setdefault("telemetry_service_name", "genericagent-harbor-lhtb")
        super().__init__(*args, **kwargs)
        self._phase = 0

    @staticmethod
    def name() -> str:
        return "generic-agent-harbor-lhtb"

    def version(self) -> str:
        return "1"

    def _task_paths(self) -> tuple[str, str]:
        agent_id = self.run_id.replace(":", "_").replace("/", "_")
        return agent_id, f"{CONTAINER_GA}/temp/{agent_id}"

    def _agent_env(self, site_packages: str) -> dict[str, str]:
        env = {
            "PYTHONPATH": f"{site_packages}:{CONTAINER_GA}",
            "GA_LANG": "en",
            "GA_OTEL_ENABLED": "1",
            "GA_OTEL_CAPTURE_CONTENT": "0",
            "GA_BENCH_RUN_ID": self.run_id,
            "GA_BENCH_TASK_ID": self.task_id,
            # Keep one OTel root open across all verifier-feedback rounds. The
            # process is terminated with the task environment, while completed
            # child spans are exported continuously.
            "GA_BENCH_EXPECTED_TURNS": "1000000",
            "GA_OTEL_ARTIFACT_DIR": "/logs/agent",
            "OTEL_SERVICE_NAME": self.telemetry_service_name,
            "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT": self.collector_endpoint,
            "GA_MAX_TURNS": str(self.max_turns),
            "GA_RESEARCH_EVENT_PATH": "/logs/agent/research_events.jsonl",
            "GA_EXPERIMENT_ID": self.experiment_id,
            "GA_CONDITION_ID": self.condition_id,
            "GA_TASK_WORKSPACE_DIR": self.task_workspace_dir,
            "GA_INLINE_LONG_PROMPT": "1",
        }
        if self.llm_config_name:
            env["GA_LLM_CONFIG_NAME"] = self.llm_config_name
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
            if self.m3_human_loop_enabled:
                env["GA_M3_HUMAN_LOOP_ENABLED"] = "1"
            if self.m3_decision_value_enabled:
                env["GA_M3_DECISION_VALUE_ENABLED"] = "1"
            if self.m3_discriminative_control_enabled:
                env["GA_M3_DISCRIMINATIVE_CONTROL_ENABLED"] = "1"
            if self.m3_combined_control_enabled:
                env["GA_M3_COMBINED_CONTROL_ENABLED"] = "1"
        import os

        for name in FORWARDED_ENV_VARS:
            value = os.environ.get(name)
            if value:
                env[name] = value
        return env

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        agent_id, task_dir = self._task_paths()
        python_bin, site_packages = _runtime_paths(self.python_home)
        output_name = "output.txt" if self._phase == 0 else f"output{self._phase}.txt"
        output = f"{task_dir}/{output_name}"

        input_name = "input.txt" if self._phase == 0 else "reply.txt"
        await self._stage_text(
            environment, f"{task_dir}/{input_name}", instruction
        )

        if self._phase == 0:
            stage = (
                f"mkdir -p {_q(task_dir)} /logs/agent && "
                f"rm -f {_q(task_dir + '/output.txt')} {_q(task_dir + '/reply.txt')} "
                f"{_q(task_dir + '/agent.pid')} {_q(task_dir + '/agent.rc')} && "
                "{ ( "
                f"{_q(python_bin)} {_q(CONTAINER_GA + '/agentmain.py')} "
                f"--task {_q(agent_id)} --llm_no {_q(self.llm_no)} "
                "--nobg --verbose --no-user-tools "
                "> /logs/agent/agent_stdout.log 2> /logs/agent/agent_stderr.log; "
                f"printf '%s\\n' \"$?\" > {_q(task_dir + '/agent.rc')} "
                f") & echo \"$!\" > {_q(task_dir + '/agent.pid')}"
                "; }"
            )
        else:
            stage = (
                f"test -s {_q(task_dir + '/agent.pid')} && "
                f"test ! -e {_q(task_dir + '/agent.rc')}"
            )

        staged = await environment.exec(
            stage,
            env=self._agent_env(site_packages),
            timeout_sec=30,
            user="root",
        )
        if staged.return_code:
            raise RuntimeError(
                f"failed to stage GA continuation phase {self._phase}: "
                f"{staged.stderr or staged.stdout}"
            )

        iterations = max(1, self.timeout_sec // 2)
        wait_command = f"""
set +e
found=0
timed_out=1
for i in $(seq 1 {iterations}); do
  if grep -Fxq {_q(ROUND_END)} {_q(output)} 2>/dev/null; then found=1; timed_out=0; break; fi
  if test -e {_q(task_dir + '/agent.rc')}; then timed_out=0; break; fi
  sleep 2
done
cp {_q(output)} {_q('/logs/agent/' + output_name)} 2>/dev/null || true
if [ "$found" -eq 1 ]; then exit 0; fi
if [ "$timed_out" -eq 1 ]; then exit 124; fi
exit 125
""".strip()
        result = await environment.exec(
            wait_command,
            cwd="/app",
            env=self._agent_env(site_packages),
            timeout_sec=self.timeout_sec + 90,
            user="root",
        )

        process_result = await environment.exec(
            f"cat {_q(task_dir + '/agent.rc')} 2>/dev/null || true",
            timeout_sec=30,
            user="root",
        )
        raw_process_rc = (process_result.stdout or "").strip()
        try:
            process_return_code = int(raw_process_rc)
        except ValueError:
            process_return_code = None

        metadata = {
            "schema_version": self.metadata_schema_version,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "llm_no": self.llm_no,
            "expected_model": self.expected_model,
            "ga_source_sha256": self.ga_source_sha256,
            "continuation_phase": self._phase,
            "persistent_session": True,
            "round_end_seen": result.return_code == 0,
            "wrapper_return_code": result.return_code,
            "ga_process_return_code": process_return_code,
        }
        context.metadata = metadata
        await environment.exec(
            "printf %s "
            + _q(base64.b64encode(json.dumps(metadata, sort_keys=True).encode()).decode())
            + f" | base64 -d > /logs/agent/lhtb_agent_phase_{self._phase}.json",
            timeout_sec=30,
            user="root",
        )
        if result.return_code:
            detail = result.stderr or result.stdout or "no process output"
            raise RuntimeError(
                f"GenericAgent did not complete continuation phase {self._phase}: "
                f"{detail}"
            )
        self._phase += 1


__all__ = ["HarborLHTBGenericAgent"]
