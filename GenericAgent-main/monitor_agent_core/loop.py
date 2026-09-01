"""Minimal persistent model/tool loop used only by Monitor Agent."""

from __future__ import annotations

import json

from .actions import MonitorAction, ToolOutcome


class MonitorLoopError(RuntimeError):
    pass


def run_review(client, system_prompt: str, wake_context: str, tools: list[dict],
               dispatch, max_turns: int = 20) -> MonitorAction:
    """Run one wake while the provider client preserves history across wakes."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": wake_context},
    ]
    for _turn in range(1, max_turns + 1):
        response = client.complete(messages, tools)
        if not response.tool_calls:
            messages = [{
                "role": "user",
                "content": (
                    "A monitor review must finish by calling wait, intervene, or—only at a pending "
                    "root-completion boundary—allow_complete. Continue your review and call one action."
                ),
            }]
            continue

        tool_results = []
        next_prompts = []
        for call in response.tool_calls:
            try:
                arguments = json.loads(call.arguments or "{}")
            except json.JSONDecodeError as exc:
                outcome = ToolOutcome({"status": "error", "error": f"Invalid tool JSON: {exc}"})
            else:
                outcome = dispatch(call.name, arguments)
            if outcome.action is not None:
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
