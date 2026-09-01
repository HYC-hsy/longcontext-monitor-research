"""The only bridge between independent Monitor Agent and GenericAgent."""

from __future__ import annotations

from monitor_agent_core.runtime import MonitorRuntime
from research_runtime import CompletionDecision


class GenericAgentMonitorAdapter:
    def __init__(self, **runtime_options):
        self.runtime = MonitorRuntime(**runtime_options)

    def archive_boundary(self, packet):
        return self.runtime.archive_boundary(packet)

    def review_completion(self, proposal, turn, provider_link=None, response_content=None):
        payload = proposal.as_payload() if hasattr(proposal, "as_payload") else {}
        outcome = self.runtime.request_completion({
            "boundary": "root_completion_proposal",
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
        return CompletionDecision(
            decision="CONTINUE", reason_codes=(outcome.reason.upper(),),
            next_prompt=outcome.message,
        )

    def close(self):
        self.runtime.close()
