"""The only bridge between independent Monitor Agent and GenericAgent."""

from __future__ import annotations

import os

from monitor_agent_core.runtime import MonitorRuntime
from research_runtime import CompletionDecision


class GenericAgentMonitorAdapter:
    def __init__(self, **runtime_options):
        deadline = os.environ.get("GA_MONITOR_RUN_DEADLINE_EPOCH")
        if deadline is not None:
            runtime_options["run_deadline_epoch"] = float(deadline)
        for environment, setting in (
            ("GA_MONITOR_GROUNDED_CONTEXT", "monitor_grounded_context"),
            ("GA_MONITOR_HANDOFF_VALIDATION", "monitor_handoff_validation"),
            ("GA_MONITOR_ADVICE_REVISION", "monitor_advice_revision"),
            ("GA_MONITOR_FEEDBACK_FOCUS", "monitor_feedback_focus"),
            ("GA_MONITOR_INQUIRY", "monitor_inquiry"),
            ("GA_MONITOR_TOOL_FEEDBACK", "monitor_tool_feedback"),
        ):
            value = os.environ.get(environment)
            if value is not None:
                if value not in {"0", "1"}:
                    raise ValueError(environment + " must be 0 or 1")
                runtime_options["model_config"] = dict(runtime_options["model_config"],
                                                       **{setting: value == "1"})
        self.runtime = MonitorRuntime(**runtime_options)

    def archive_boundary(self, packet):
        return self.runtime.archive_boundary(packet)

    def review_completion(self, proposal, turn, provider_link=None, response_content=None):
        payload = proposal.as_payload() if hasattr(proposal, "as_payload") else {}
        outcome = self.runtime.request_completion({
            "boundary": "task_control_handoff",
            "internal_turn": turn,
            "response_content": response_content or "",
            "completion_proposal": payload,
            "provider_link": provider_link,
            "tool_calls": [],
            "tool_results": [],
        })
        if outcome.allow:
            return CompletionDecision(
                decision="ALLOW_COMPLETE", reason_codes=("MONITOR_ALLOWED",)
            )
        if outcome.incomplete:
            return CompletionDecision(
                decision="ERROR_FAIL_CLOSED",
                reason_codes=("MONITOR_REVIEW_INCOMPLETE", outcome.reason.upper()),
                next_prompt=outcome.message,
            )
        return CompletionDecision(
            decision="CONTINUE", reason_codes=(outcome.reason.upper(),),
            next_prompt=outcome.message,
        )

    def close(self):
        self.runtime.close()
