"""Single-use host-only static PMA screen, reusing the upstream PMA call path."""
from __future__ import annotations

import asyncio
from dataclasses import asdict, is_dataclass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Callable

from static_source_screen import (ASSET_REGISTRY, BATCH_SCHEMA, HERE, MANIFEST, MANIFEST_V2,
                                  ordered_slots, plan_slots, projected_events, selected_cases,
                                  sha256, verify_public_projection)
from episode import PMAEpisode, construct_upstream
import litellm


def append_json(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, default=str, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def public_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if is_dataclass(value):
        return public_value(asdict(value))
    if isinstance(value, dict):
        return {str(k): public_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [public_value(v) for v in value]
    if hasattr(value, "model_dump"):
        return public_value(value.model_dump())
    if hasattr(value, "__dict__"):
        return public_value(vars(value))
    return str(value)


def profile_identity(path: Path) -> tuple[dict, dict]:
    source = json.loads(path.read_text(encoding="utf-8"))
    profile = source["claude_monitor_opus48"]
    if (profile.get("provider"), profile.get("api_mode"), profile.get("model"),
            profile.get("thinking_type")) != ("anthropic", "messages", "claude-opus-4-8", "adaptive"):
        raise ValueError("frozen PMA model profile mismatch")
    if not profile.get("apikey") or not profile.get("apibase"):
        raise ValueError("private model transport absent")
    safe = {key: profile.get(key) for key in (
        "provider", "api_mode", "model", "thinking_type", "reasoning_effort",
        "temperature", "max_tokens", "timeout", "read_timeout", "max_retries")}
    safe.update(profile_file_sha256=sha256(path), private_transport_present=True,
                effective_upstream_retry_attempts=3)
    return profile, safe


def code_commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE,
                          capture_output=True, text=True, check=True).stdout.strip()


def authorize(manifest_path: Path, auth_path: Path, output: Path, profile_path: Path) -> tuple[dict, dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    is_v2 = manifest.get("schema") == "pma-source-memory-static-live-batch-v2"
    is_v3 = manifest.get("schema") == BATCH_SCHEMA
    if is_v3:
        try:
            slots = plan_slots(manifest)
        except (ValueError, KeyError, TypeError) as exc:
            raise PermissionError("v3 plan or fixed asset identity mismatch") from exc
        if manifest.get("code_commit") != code_commit():
            raise PermissionError("frozen run code identity mismatch")
    else:
        frozen = json.loads((MANIFEST_V2 if is_v2 else MANIFEST).read_text(encoding="utf-8"))
        if (manifest.get("schema") not in {"pma-source-memory-static-live-batch-v1",
                                          "pma-source-memory-static-live-batch-v2"} or
                manifest.get("conditions") != frozen["conditions"] or
                manifest.get("cases") != frozen["cases"] or
                manifest.get("input_policy") != frozen["input_policy"] or
                (is_v2 and manifest.get("planned_order") != frozen["planned_order"])):
            raise PermissionError("static candidate or public-input identity mismatch")
        slots = plan_slots(manifest)
    bindings = manifest.get("run_bindings")
    expected = [(slot["case_id"], slot["variant"]) for slot in slots]
    if (manifest.get("execution_authorized") is not False or
            not isinstance(bindings, list) or len(bindings) != len(slots) or
            [(b.get("task"), b.get("variant")) for b in bindings] != expected or
            [b.get("order") for b in bindings] != list(range(1, len(slots) + 1)) or
            len({b.get("run_id") for b in bindings}) != len(slots) or
            (is_v3 and any((b.get("case_id"), b.get("occurrence")) !=
                           (slot["case_id"], slot["occurrence"])
                           for b, slot in zip(bindings, slots, strict=True)))):
        raise PermissionError("frozen static manifest invalid")
    if (auth.get("execution_authorized") is not True or
            auth.get("manifest_sha256") != sha256(manifest_path) or
            auth.get("code_commit") != code_commit() or
            auth.get("profile_sha256") != sha256(profile_path) or
            auth.get("run_bindings") != bindings or
            (is_v3 and (auth.get("batch_id") != manifest.get("batch_id") or
                        auth.get("asset_registry_sha256") != sha256(ASSET_REGISTRY))) or
            auth.get("output_root") != str(output.resolve()) or
            output.exists()):
        raise PermissionError("single-use static authorization/identity mismatch")
    if len({b.get("run_id") for b in bindings}) != len(bindings):
        raise PermissionError("duplicate run identity")
    for binding in bindings:
        run_id = binding["run_id"]
        if (not isinstance(run_id, str) or run_id in {"", ".", ".."} or
                "/" in run_id or "\\" in run_id):
            raise PermissionError("run ID must be one nonempty path segment")
        path = (output / binding["run_id"]).resolve()
        if (not path.is_relative_to(output.resolve()) or path.exists() or
                ((is_v2 or is_v3) and binding.get("run_root") != str(path))):
            raise PermissionError("run root exists or escapes batch")
    # Identity and public projection checks are pre-send gates, not observations.
    for case in selected_cases(manifest).values():
        verify_public_projection(case)
    return manifest, auth


async def run_authorized(manifest_path: Path, auth_path: Path, profile_path: Path,
                         output: Path, *, fake_transport_factory: Callable | None = None) -> list[dict]:
    manifest, auth = authorize(manifest_path, auth_path, output, profile_path)
    profile, safe_profile = profile_identity(profile_path)
    output.mkdir(parents=True, exist_ok=False)
    (output / "authorization_consumed.json").write_text(json.dumps({
        "manifest_sha256": sha256(manifest_path), "code_commit": code_commit(),
        "profile": safe_profile, "bindings": manifest["run_bindings"]}, indent=2), encoding="utf-8")
    results = []
    try:
        cases = selected_cases(manifest)
        for identity in plan_slots(manifest):
                task, variant = identity["case_id"], identity["variant"]
                case = cases[task]
                mapping = verify_public_projection(case)
                binding = manifest["run_bindings"][len(results)]
                slot = output / binding["run_id"]
                slot.mkdir()
                (slot / "public_mapping.json").write_text(json.dumps(mapping, indent=2), encoding="utf-8")
                events = projected_events(case, binding["run_id"])
                agent = construct_upstream(slot / "upstream", memory_profile=profile,
                                           research_candidate=variant)
                if fake_transport_factory is not None:
                    agent._memory_llm.call = fake_transport_factory(variant, slot)
                logical = 0
                lower = 0
                failures = []
                capture_error = None
                terminal_failure = None
                blocked_phase_calls = 0
                original = agent._memory_llm.call
                original_lower = litellm.acompletion

                async def observed_lower(**kwargs):
                    nonlocal lower, capture_error
                    if capture_error is not None:
                        raise RuntimeError("provider capture integrity already failed")
                    lower += 1
                    number = lower
                    try:
                        append_json(slot / "provider_attempts.jsonl", {
                            "attempt": number, "started_epoch": time.time(),
                            "model": kwargs.get("model"), "max_tokens": kwargs.get("max_tokens"),
                            "temperature": kwargs.get("temperature"),
                            "thinking": kwargs.get("thinking"),
                            "reasoning_effort": kwargs.get("reasoning_effort"),
                            "timeout": kwargs.get("timeout"),
                            "messages": public_value(kwargs.get("messages")),
                            "tools": public_value(kwargs.get("tools"))})
                    except Exception as exc:
                        capture_error = exc
                        raise
                    try:
                        response = await original_lower(**kwargs)
                        try:
                            append_json(slot / "provider_attempts.jsonl", {
                                "attempt": number, "outcome": "returned", "ended_epoch": time.time(),
                                "returned_model": response.get("model"),
                                "choices": public_value(response.get("choices")),
                                "usage": public_value(response.get("usage"))})
                        except Exception as exc:
                            # The provider may have executed. Do not raise here:
                            # upstream LiteLLM would retry the accepted request.
                            capture_error = exc
                        return response
                    except BaseException as exc:
                        try:
                            append_json(slot / "provider_attempts.jsonl", {
                                "attempt": number, "outcome": "exception", "error_type": type(exc).__name__,
                                "server_execution": "unknown", "ended_epoch": time.time()})
                        except Exception as capture_exc:
                            capture_error = capture_exc
                        raise

                async def audited_call(*, prompt, system, tools=None):
                    nonlocal logical, capture_error, terminal_failure, blocked_phase_calls
                    phase = "phase1" if tools is not None else "phase2"
                    if terminal_failure is not None:
                        blocked_phase_calls += 1
                        append_json(slot / "blocked_requests.jsonl", {
                            "phase": phase, "epoch": time.time(), "sent": False,
                            "reason": "prior_logical_request_terminal_failure",
                            "prior_error_type": type(terminal_failure).__name__})
                        raise RuntimeError("prior logical provider request failed; no further send") from terminal_failure
                    if capture_error is not None:
                        raise RuntimeError("capture integrity failed; no subsequent model send") from capture_error
                    logical += 1
                    number = logical
                    try:
                        append_json(slot / "requests.jsonl", {"logical_call": number,
                            "phase": phase, "started_epoch": time.time(), "system": system,
                            "prompt": prompt, "tools": tools})
                    except Exception as exc:
                        capture_error = exc
                        raise
                    try:
                        response = await original(prompt=prompt, system=system, tools=tools)
                        if capture_error is not None:
                            raise RuntimeError("provider response capture failed") from capture_error
                        try:
                            append_json(slot / "responses.jsonl", {"logical_call": number,
                                "phase": phase, "ended_epoch": time.time(), "status": "returned",
                                "content": response.content, "tool_calls": public_value(response.tool_calls),
                                "usage": public_value(response.usage)})
                        except Exception as exc:
                            capture_error = exc
                            raise
                        return response
                    except BaseException as exc:
                        terminal_failure = exc
                        failures.append({"logical_call": number, "phase": phase,
                                         "error_type": type(exc).__name__})
                        try:
                            append_json(slot / "responses.jsonl", {"logical_call": number,
                                "phase": phase, "ended_epoch": time.time(), "status": "exception",
                                "error_type": type(exc).__name__, "server_execution": "unknown"})
                        except Exception as capture_exc:
                            capture_error = capture_exc
                        raise

                agent._memory_llm.call = audited_call
                episode = PMAEpisode(agent, run_id=binding["run_id"], task_id=case["task"],
                                     archive=slot / "episode")
                slot_started = time.time()
                status = "static_prefix_complete"
                error_type = None
                litellm.acompletion = observed_lower
                try:
                    for event in events:
                        before = len(failures)
                        await episode.handle(event)
                        fatal = getattr(agent._memory_agent, "_fatal_error", None)
                        if fatal is not None:
                            raise RuntimeError("candidate host integrity failure") from fatal
                        if capture_error is not None:
                            raise RuntimeError("static provider capture integrity failed") from capture_error
                        append_json(slot / "bank_states.jsonl", {"sequence": event["sequence"],
                            "memory": agent.memory.to_dict(),
                            "reminder_status": getattr(agent._memory_agent, "last_delivery_status", "upstream")})
                        if len(failures) != before:
                            raise RuntimeError("upstream caught a provider phase failure; stop batch")
                    agent.save_memory(str(slot / "memory.json"))
                    if not (slot / "memory.json").is_file() or not (slot / "trajectory_memory.json").is_file():
                        raise RuntimeError("upstream bank or trajectory was not persisted")
                except BaseException as exc:
                    status = "stopped_failure"
                    error_type = type(exc).__name__
                    try:
                        agent.save_memory(str(slot / "failure_memory.json"))
                    except Exception:
                        pass
                finally:
                    litellm.acompletion = original_lower
                row = {"order": binding["order"], "run_id": binding["run_id"],
                       "occurrence": identity["occurrence"],
                       "task": case["task"], "variant": variant, "status": status,
                       "error_type": error_type, "logical_phase_calls": logical,
                       "observable_litellm_calls": lower,
                       "blocked_phase_calls": (blocked_phase_calls + getattr(
                           agent._memory_agent, "blocked_phase2_attempts", 0)),
                       "inner_network_attempts": "unknown", "phase_failures": failures,
                       "started_epoch": slot_started, "ended_epoch": time.time(),
                       "persisted_artifacts": {name: sha256(slot / name)
                           for name in ("memory.json", "trajectory_memory.json",
                                        "failure_memory.json") if (slot / name).is_file()},
                       "task_calls": 0, "native_evaluator_calls": 0,
                       "input_sent_to_task": False, "task_completed": False}
                (slot / "result.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
                results.append(row)
                (output / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
                print(json.dumps({"order": binding["order"], "status": status,
                                  "logical_phase_calls": logical,
                                  "observable_litellm_calls": lower}), flush=True)
                if status != "static_prefix_complete":
                    return results
    finally:
        # This batch authorization never confers authority on a second invocation.
        auth_path.unlink(missing_ok=True)
    return results
