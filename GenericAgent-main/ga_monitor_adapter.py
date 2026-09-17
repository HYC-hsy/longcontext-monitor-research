"""The only bridge between independent Monitor Agent and GenericAgent."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from monitor_agent_core.runtime import MonitorRuntime
from monitor_agent_core.configuration import load_profile
from research_runtime import CompletionDecision


def monitor_profile(name):
    bundled = Path(__file__).parent / 'monitor_agent_core' / 'models.local.json'
    path = os.environ.get('MONITOR_CONFIG_FILE') or (
        bundled if bundled.exists() else Path(__file__).parent.parent / 'monitor_config' / 'models.local.json')
    return load_profile(name, path)


def public_observation(packet):
    event = dict(packet)
    event['task_turn'] = int(event.pop('internal_turn', 0) or 0)
    event['text'] = str(event.pop('response_content', '') or '')
    summaries = re.findall(r'<summary[^>]*>(.*?)</summary>', event['text'], re.I | re.S)
    event['synopsis'] = (summaries[-1].strip() if summaries else event['text'].strip())[:600]
    calls = []
    for original in event.get('tool_calls') or []:
        call = dict(original)
        call['name'] = call.pop('tool_name', call.get('name', ''))
        calls.append(call)
    event['tool_calls'] = calls
    return event


class GenericAgentMonitorAdapter:
    def __init__(self, **runtime_options):
        if os.environ.get('GA_MONITOR_HYBRID_CONTROL', '0') != '0':
            raise ValueError('GA_MONITOR_HYBRID_CONTROL retired: model-requested pause was removed')
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
            ("GA_MONITOR_ACTIVE_WORKING_CONTEXT", "monitor_active_working_context"),
            ("GA_MONITOR_LIVE_AWARENESS", "monitor_live_awareness"),
            ("GA_MONITOR_DECISION_CONTEXT", "monitor_decision_context"),
            ("GA_MONITOR_PMA_MEMORY", "monitor_pma_memory"),
            ("GA_MONITOR_ROOT_DECISION_CONTRACT", "monitor_root_decision_contract"),
            ("GA_MONITOR_TASK_MODEL", "monitor_task_model"),
        ):
            value = os.environ.get(environment)
            if value is not None:
                if value not in {"0", "1"}:
                    raise ValueError(environment + " must be 0 or 1")
                runtime_options["model_config"] = dict(runtime_options["model_config"],
                                                       **{setting: value == "1"})
        original = Path(runtime_options['task_workspace']) / f'.monitor_original_task_{uuid.uuid4().hex}.txt'
        with original.open('x', encoding='utf-8') as stream:
            stream.write(runtime_options['public_task'])
        runtime_options['task_original_path'] = str(original)
        runtime_options.setdefault('task_id', os.environ.get('GA_BENCH_RUN_ID') or uuid.uuid4().hex)
        try:
            self.runtime = MonitorRuntime(**runtime_options)
        except Exception:
            original.unlink(missing_ok=True)
            raise

    def archive_boundary(self, packet):
        return self.runtime.archive_boundary(public_observation(packet))

    def review_completion(self, proposal, turn, provider_link=None, response_content=None):
        payload = proposal.as_payload() if hasattr(proposal, "as_payload") else {}
        outcome = self.runtime.request_completion(public_observation({
            "boundary": "task_control_handoff",
            "internal_turn": turn,
            "response_content": response_content or "",
            "completion_proposal": payload,
            "provider_link": provider_link,
            "tool_calls": [],
            "tool_results": [],
        }))
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
