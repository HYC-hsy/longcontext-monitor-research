"""Bind the opt-in predictive PMA to one explicit model profile.

This module selects configuration only. It does not change PMA prompts,
memory operations, trigger cadence, or task-agent settings.
"""

from __future__ import annotations

import json


READ_CONTEXT = "pma_predictive_read_context_v1"
CLAUDE_MODELS = {"claude-opus-4-8", "claude-opus-5", "claude-fable-5"}
OPENAI_MODELS = {"gpt-6.1-sol", "gpt-6-sol", "gpt-6-astra"}


def load_profile(raw: bytes, candidate: str) -> tuple[str, dict]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("PMA profile container must be an object")
    if candidate == READ_CONTEXT and set(data) == {"pma_model"}:
        name = "pma_model"
    else:
        name = "claude_monitor_opus48"
    profile = data.get(name)
    if not isinstance(profile, dict):
        raise ValueError("bound PMA model profile is missing")
    if not profile.get("apibase") or not profile.get("apikey"):
        raise ValueError("PMA model profile lacks transport configuration")
    request_summary = profile.get("request_public_summary", False)
    if type(request_summary) is not bool:
        raise ValueError("request_public_summary must be a boolean")
    if request_summary and (candidate != READ_CONTEXT or
            (profile.get("provider"), profile.get("api_mode")) != ("openai", "responses")):
        raise ValueError("public summary requests are supported only by the Responses adapter")
    if candidate != READ_CONTEXT:
        expected = ("anthropic", "messages", "claude-opus-4-8", "adaptive")
        actual = tuple(profile.get(k) for k in
                       ("provider", "api_mode", "model", "thinking_type"))
        if actual != expected:
            raise ValueError("non-candidate PMA profile differs from Opus 4.8")
        return name, profile
    model = profile.get("model")
    if model in CLAUDE_MODELS:
        if (profile.get("provider"), profile.get("api_mode"),
                profile.get("thinking_type")) != ("anthropic", "messages", "adaptive"):
            raise ValueError("Claude PMA profile route differs")
        if profile.get("temperature") != 1:
            raise ValueError("Claude PMA temperature differs")
    elif model in OPENAI_MODELS:
        if (profile.get("provider"), profile.get("api_mode")) != ("openai", "responses"):
            raise ValueError("GPT PMA profile must use Responses API")
        if "temperature" in profile or "thinking_type" in profile or profile.get("store") is not False:
            raise ValueError("GPT PMA profile has unsupported or stored-response settings")
        if (not isinstance(profile.get("model_context_window"), int) or
                profile["model_context_window"] <= profile.get("max_tokens", 0)):
            raise ValueError("GPT PMA context window must be explicit")
    else:
        raise ValueError("PMA model is not in the frozen comparison")
    if profile.get("reasoning_effort") != "high":
        raise ValueError("PMA reasoning effort identity differs")
    if profile.get("max_tokens") != 8192:
        raise ValueError("PMA output-token limit identity differs")
    if not isinstance(profile.get("read_timeout"), (int, float)) or profile["read_timeout"] <= 0:
        raise ValueError("PMA request timeout missing")
    if not isinstance(profile.get("max_retries"), int) or profile["max_retries"] < 0:
        raise ValueError("PMA retry setting missing")
    return name, profile
