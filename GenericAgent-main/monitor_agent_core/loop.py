"""Minimal persistent model/tool loop used only by Monitor Agent."""

from __future__ import annotations

import json

from .actions import MonitorAction, ToolOutcome


class MonitorLoopError(RuntimeError):
    pass


def run_review(client, system_prompt: str, wake_context: str, tools: list[dict],
               dispatch, max_turns: int = 20, audit=None) -> MonitorAction:
    """Run one wake while the provider client preserves history across wakes."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": wake_context},
    ]
    def record(event, **payload):
        if audit is not None:
            audit(event, **payload)

    record('review_context', system_prompt=system_prompt, wake_context=wake_context, tools=tools)
    for _turn in range(1, max_turns + 1):
        # Record deltas, not a second copy of the entire growing provider history.
        record('model_input', turn=_turn, messages=messages)
        try:
            response = client.complete(messages, tools)
        except Exception as exc:
            record('model_error', turn=_turn, error_type=type(exc).__name__)
            raise
        record('model_output', turn=_turn, content=response.content,
               tool_calls=[{'id': c.id, 'name': c.name, 'arguments': c.arguments}
                           for c in response.tool_calls], usage=response.usage)
        if not response.tool_calls:
            messages = [{
                "role": "user",
                "content": (
                    "Continue using the available tools as needed. Follow the current system instructions "
                    "for when to send input and when to end this review."
                ),
            }]
            continue

        tool_results = []
        next_prompts = []
        for index, call in enumerate(response.tool_calls):
            record('tool_call', turn=_turn, tool_id=call.id, name=call.name, arguments=call.arguments)
            try:
                arguments = json.loads(call.arguments or "{}")
            except json.JSONDecodeError as exc:
                outcome = ToolOutcome({"status": "error", "error": f"Invalid tool JSON: {exc}"})
            else:
                try:
                    outcome = dispatch(call.name, arguments)
                except Exception as exc:
                    record('tool_error', turn=_turn, tool_id=call.id, error_type=type(exc).__name__)
                    raise
            record('tool_result', turn=_turn, tool_id=call.id, data=outcome.data,
                   action=({'kind': outcome.action.kind, 'payload': outcome.action.payload}
                           if outcome.action is not None else None))
            if outcome.action is not None:
                completed = tool_results + [{
                    "tool_use_id": call.id,
                    "content": json.dumps({
                        "status": "accepted", "control_action": outcome.action.kind,
                    }),
                }]
                completed.extend({
                    "tool_use_id": pending.id,
                    "content": json.dumps({
                        "status": "not_executed", "reason": "review_control_action_selected",
                    }),
                } for pending in response.tool_calls[index + 1:])
                record('control_result', turn=_turn, results=completed)
                record_results = getattr(client, "record_tool_results", None)
                if record_results is not None:
                    record_results(completed)
                return outcome.action
            tool_results.append({
                "tool_use_id": call.id,
                "content": json.dumps(outcome.data, ensure_ascii=False, default=str),
            })
            if outcome.continue_review:
                next_prompts.append("Continue the same review and finish with one control action.")
        messages = [{
            "role": "user",
            "content": "\n".join(next_prompts) or "Continue.",
            "tool_results": tool_results,
        }]
    raise MonitorLoopError(f"Monitor review exceeded {max_turns} turns without a control action")
