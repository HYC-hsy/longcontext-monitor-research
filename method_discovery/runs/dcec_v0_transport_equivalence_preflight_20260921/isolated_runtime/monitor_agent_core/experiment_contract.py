"""Fail-closed model identity contract for frozen Monitor experiments."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


PUBLIC_FIELDS = (
    "model", "provider", "api_mode", "thinking_type", "reasoning_effort",
    "temperature", "max_tokens", "context_win", "timeout", "read_timeout",
    "max_retries", "transport_route", "stream", "endpoint_host",
)


def _normal(value):
    return value.lower() if isinstance(value, str) else value


def resolved_monitor_config(profile: str, config: dict) -> dict:
    base = config.get("apibase") or config.get("base_url") or ""
    provider = config.get("provider") or "anthropic"
    api_mode = config.get("api_mode") or ("messages" if provider == "anthropic" else None)
    values = {
        "profile": profile,
        "model": config.get("model"),
        "provider": provider,
        "api_mode": api_mode,
        "thinking_type": config.get("thinking_type"),
        "reasoning_effort": config.get("reasoning_effort"),
        "temperature": config.get("temperature", 1),
        "max_tokens": config.get("max_tokens", 8192),
        "context_win": config.get("context_win", 30000),
        "timeout": config.get("timeout", 5),
        "read_timeout": config.get("read_timeout", 40),
        "max_retries": config.get("max_retries", 4),
        "transport_route": config.get("transport_route"),
        "stream": config.get("stream", True),
        "endpoint_host": urlparse(base).hostname or "",
    }
    return {key: values.get(key) for key in ("profile",) + PUBLIC_FIELDS}


def resolved_task_client(profile: str, client) -> dict:
    backend = getattr(client, "backend", client)
    class_name = type(backend).__name__
    is_claude = class_name == "NativeClaudeSession"
    is_oai = class_name == "NativeOAISession"
    base = getattr(backend, "api_base", "")
    values = {
        "profile": profile,
        "model": getattr(backend, "model", None),
        "provider": "anthropic" if is_claude else "openai" if is_oai else class_name,
        "api_mode": "messages" if is_claude else getattr(backend, "api_mode", None),
        "thinking_type": getattr(backend, "thinking_type", None),
        "reasoning_effort": getattr(backend, "reasoning_effort", None),
        "temperature": getattr(backend, "temperature", None),
        "max_tokens": getattr(backend, "max_tokens", None),
        "context_win": getattr(backend, "context_win", None),
        "timeout": getattr(backend, "connect_timeout", None),
        "read_timeout": getattr(backend, "read_timeout", None),
        "max_retries": getattr(backend, "max_retries", None),
        "transport_route": "task",
        "stream": getattr(backend, "stream", None),
        "endpoint_host": urlparse(base).hostname or "",
    }
    return {key: values.get(key) for key in ("profile",) + PUBLIC_FIELDS}


def load_contract(path) -> dict:
    source = Path(path)
    contract = json.loads(source.read_text(encoding="utf-8"))
    if contract.get("schema_version") != "monitor-experiment-model-contract/1":
        raise ValueError("unsupported experiment model contract")
    if contract.get("allow_model_fallback") is not False:
        raise ValueError("experiment model contract must disable fallback")
    return contract


def validate_role(contract: dict, role: str, actual: dict) -> None:
    expected = (contract.get("roles") or {}).get(role)
    if not isinstance(expected, dict):
        raise ValueError(f"model contract has no role: {role}")
    expected = expected.get("resolved")
    if not isinstance(expected, dict):
        raise ValueError(f"model contract role {role} has no resolved configuration")
    for field, wanted in expected.items():
        got = actual.get(field)
        if _normal(got) != _normal(wanted):
            raise ValueError(
                f"model contract mismatch: role={role} field={field} "
                f"expected={wanted!r} actual={got!r}"
            )


def validate_source_upstream(contract: dict, role: str, actual: dict) -> None:
    expected = (contract.get("roles") or {}).get(role) or {}
    source = expected.get("source")
    if not isinstance(source, dict):
        raise ValueError(f"model contract role {role} has no source configuration")
    for field, wanted in source.items():
        got = actual.get(field)
        if _normal(got) != _normal(wanted):
            raise ValueError(
                f"model source mismatch: role={role} field={field} "
                f"expected={wanted!r} actual={got!r}"
            )


def validate_inherited_child(contract: dict, supervisor: dict,
                             child: dict | None = None) -> dict:
    rule = (contract.get("roles") or {}).get("independent_c") or {}
    if rule.get("inherits") != "supervisor":
        raise ValueError("independent_c must inherit the supervisor model configuration")
    resolved = dict(supervisor if child is None else child)
    for field in ("model", "provider", "api_mode", "thinking_type", "reasoning_effort",
                  "temperature", "max_tokens", "context_win", "endpoint_host"):
        if _normal(resolved.get(field)) != _normal(supervisor.get(field)):
            raise ValueError(
                f"model contract mismatch: role=independent_c field={field} "
                f"must inherit supervisor"
            )
    return resolved


def validate_live_roles(contract: dict, task: dict, supervisor: dict,
                        child_override: str | None = None,
                        child: dict | None = None) -> dict:
    """Production pre-request gate shared by the host and offline regressions."""
    validate_role(contract, "task_agent", task)
    validate_role(contract, "supervisor", supervisor)
    if child_override:
        raise ValueError(
            "independent_c has an independent profile/config; it must inherit supervisor")
    inherited = validate_inherited_child(contract, supervisor, child)
    return {
        "contract_id": contract.get("contract_id"),
        "allow_model_fallback": False,
        "roles": {
            "task_agent": dict(task),
            "supervisor": dict(supervisor),
            "independent_c": {"inherits": "supervisor", "resolved": inherited},
        },
    }
