"""The only bridge between independent Monitor Agent and GenericAgent."""

from __future__ import annotations

from monitor_agent_core.runtime import MonitorRuntime
from research_runtime import CompletionDecision


class GenericAgentMonitorAdapter:
    def __init__(self, **runtime_options):
        self.runtime = MonitorRuntime(**runtime_options)

    def archive_boundary(self, packet):
        return self.runtime.archive_boundary(packet)

    def consume_interventions(self):
        # The runtime delivers corrections immediately through GA's resumable
        # interruption callback; no delayed packet is consumed at inference.
        return []

    def review_completion(self, proposal, turn, provider_link=None, response_content=None):
        outcome = self.runtime.request_completion()
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
