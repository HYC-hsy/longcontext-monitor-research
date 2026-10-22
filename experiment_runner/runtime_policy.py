"""Strict, serializable runtime limits and the pinned Harbor runtime overlay.

This module changes execution policy, not a task asset or verifier protocol.
It does not authorize execution, certify a manifest, or interpret model output.
"""
from copy import copy, deepcopy
import json
import math

SCHEMA = "experiment_runtime_policy_v1"
HARBOR_COMMIT = "459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc"
_CACHES = ("_verifier_timeout_sec", "_agent_setup_timeout_sec",
           "_environment_build_timeout_sec")


def _positive(value, name, integer=False):
    types = (int,) if integer else (int, float)
    if type(value) not in types or value <= 0:
        raise ValueError(f"{name} must be a positive {'integer' if integer else 'number'}")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError(f"{name} must be finite")
    return int(value) if type(value) is float and value.is_integer() else value


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("policy must contain finite JSON data") from exc


def resolve_policy(requested, asset, method_defaults):
    """Resolve explicit user options without treating null as 'uncapped'."""
    if not isinstance(requested, dict):
        raise ValueError("requested must be a dictionary")
    if set(requested) - {"agent_timeout", "task_turns", "verifier_timeout"}:
        raise ValueError("unknown runtime policy fields")
    if not isinstance(asset, dict) or not isinstance(method_defaults, dict):
        raise ValueError("asset and method_defaults must be dictionaries")
    official_agent = _positive(asset.get("native_agent_seconds"), "official agent timeout")
    official_verifier = _positive(asset.get("native_verifier_seconds"), "official verifier timeout")
    if "task_turns_max" not in method_defaults:
        raise ValueError("method default task_turns_max is required")
    default_turns = method_defaults["task_turns_max"]
    if default_turns is not None:
        _positive(default_turns, "method default task turns", integer=True)
    agent = requested.get("agent_timeout", "official")
    turns = requested.get("task_turns", "method_default")
    verifier = requested.get("verifier_timeout", "official")
    if agent == "official":
        effective_agent = official_agent
    elif agent == "uncapped":
        effective_agent = None
    else:
        effective_agent = _positive(agent, "agent_timeout")
    if turns == "method_default":
        effective_turns = default_turns
    elif turns == "uncapped":
        effective_turns = None
    else:
        effective_turns = _positive(turns, "task_turns", integer=True)
    if verifier != "official":
        raise ValueError("verifier_timeout must remain official")
    return {
        "schema": SCHEMA,
        "requested": {"agent_timeout": agent, "task_turns": turns,
                      "verifier_timeout": verifier},
        "official_agent_seconds": official_agent,
        "official_verifier_seconds": official_verifier,
        "effective_agent_seconds": effective_agent,
        "effective_task_turns": effective_turns,
        # Harbor owns phase-local limits. A sum measured before setup/build
        # can kill a valid verifier, so explicit policies add no aggregate cap.
        "outer_timeout_seconds": None,
        "supervision": "phase_local",
        "method_default_task_turns": default_turns,
        "protocol_label": ("official_agent_limits" if agent == "official" and turns == "method_default"
                           else "diagnostic_agent_override"),
    }


def validate_resolved_policy(policy, asset):
    """Reject missing/extra fields and derived-value tampering, including bools."""
    if not isinstance(policy, dict) or "method_default_task_turns" not in policy:
        raise ValueError("resolved policy is incomplete")
    expected = resolve_policy(policy.get("requested"), asset,
                              {"task_turns_max": policy["method_default_task_turns"]})
    if _canonical(expected) != _canonical(policy):
        raise ValueError("resolved policy does not match its inputs and task asset")
    return deepcopy(expected)


def _clone(value):
    copier = getattr(value, "model_copy", None)
    result = copier(deep=True) if callable(copier) else deepcopy(value)
    if result is value:
        raise ValueError("runtime configuration must support independent deep copying")
    return result


def _required(obj, attr):
    if not hasattr(obj, attr):
        raise ValueError(f"unsupported pinned Harbor interface: missing {attr}")
    return getattr(obj, attr)


def apply_harbor_policy(trial, policy):
    """Apply once after Trial initialization, preserving all non-agent timeouts.

    Caller must verify the manifest binding and pinned Harbor installation first.
    No raw task files are read or written. A receipt is attached to the Trial.
    Reapplying is rejected rather than confusing original and effective limits.
    """
    if hasattr(trial, "_experiment_runtime_policy_receipt"):
        raise ValueError("runtime policy has already been applied to this Trial")
    task = _required(trial, "task")
    task_config = _required(task, "config")
    config = _required(trial, "config")
    task_agent = _required(task_config, "agent")
    task_verifier = _required(task_config, "verifier")
    config_agent = _required(config, "agent")
    asset = {"native_agent_seconds": _required(task_agent, "timeout_sec"),
             "native_verifier_seconds": _required(task_verifier, "timeout_sec")}
    checked = validate_resolved_policy(policy, asset)
    original = {
        "task_agent_seconds": asset["native_agent_seconds"],
        "override_timeout_sec": _required(config_agent, "override_timeout_sec"),
        "max_timeout_sec": _required(config_agent, "max_timeout_sec"),
        "agent_timeout_multiplier": _required(config, "agent_timeout_multiplier"),
        "cached_agent_seconds": _required(trial, "_agent_timeout_sec"),
    }
    caches = {name: deepcopy(_required(trial, name)) for name in _CACHES}
    compute = _required(trial, "_compute_agent_timeout_sec")
    if not callable(compute):
        raise ValueError("unsupported Harbor agent timeout computation")
    # Clone the task wrapper too: two Trial instances may share the Task itself.
    task_copy = copy(task)
    if task_copy is task:
        raise ValueError("Task must support an independent wrapper copy")
    task_copy.config = _clone(task_config)
    config_copy = _clone(config)
    task_copy.config.agent.timeout_sec = checked["effective_agent_seconds"]
    config_copy.agent.override_timeout_sec = None
    config_copy.agent.max_timeout_sec = None
    config_copy.agent_timeout_multiplier = 1
    try:
        trial.task = task_copy
        trial.config = config_copy
        trial._agent_timeout_sec = compute()
        actual = trial._agent_timeout_sec
        expected = checked["effective_agent_seconds"]
        if ((expected is None and actual is not None) or
                (expected is not None and (type(actual) not in (int, float) or actual != expected))):
            raise ValueError("Harbor effective agent timeout does not match runtime policy")
        if any(_canonical(getattr(trial, key)) != _canonical(value)
               for key, value in caches.items()):
            raise ValueError("Harbor overlay changed a non-agent cached timeout")
        receipt = {
            "schema": "harbor_runtime_policy_receipt_v1",
            "harbor_commit": HARBOR_COMMIT,
            "protocol_label": checked["protocol_label"],
            "runtime_policy": checked,
            "original": original,
            "effective_agent_seconds": trial._agent_timeout_sec,
            "preserved_timeout_caches": caches,
            "task_files_modified": False,
        }
        trial._experiment_runtime_policy_receipt = deepcopy(receipt)
        return receipt
    except BaseException:
        trial.task = task
        trial.config = config
        trial._agent_timeout_sec = original["cached_agent_seconds"]
        for key, value in caches.items():
            setattr(trial, key, value)
        raise
