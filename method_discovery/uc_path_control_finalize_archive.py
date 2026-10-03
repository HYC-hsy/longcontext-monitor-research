"""Correct mechanical counts and add request/window/intervention locators; no inference."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import sys
import zipfile

from method_discovery.uc_path_control_archive import RECORDS, rows, write
from method_discovery.uc_path_control_entry import PLAN, PLAN_ROOT, REPO
sys.path.insert(0, str(REPO / "GenericAgent-main"))
from monitor_agent_core.agent import DCEC_SYSTEM_PROMPT
from monitor_agent_core.path_control_v0 import SYSTEM_PROMPT, WORKING_GUIDANCE


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)


def finalize(slot):
    root = RECORDS / f"{slot['position']:02d}_{slot['run_id']}"
    facts_path = root / "MECHANICAL_SUMMARY.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    task = rows(root / "agent/research_events.jsonl")
    usage = [e["payload"] for e in task if e.get("event_type") == "provider_usage"
             and isinstance(e.get("payload"), dict)]
    fields = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens", "cached_input_tokens")
    facts["task_usage_observations"] = len(usage)
    facts["task_tokens_observed"] = {
        key: sum(e.get(key) or 0 for e in usage) if usage else None for key in fields}
    manifest = json.loads((root / "runner/manifest.json").read_text(encoding="utf-8"))
    facts["trial_outcome"] = manifest.get("trial_outcome")
    facts["observed_models"] = manifest.get("trace", {}).get("observed_models")
    result = json.loads((root / "trial/result.json").read_text(encoding="utf-8"))
    agent_result = result.get("agent_result") or {}
    facts["harbor_agent_usage"] = {
        key: agent_result.get(key) for key in (
            "n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")}
    facts["completion_proposals"] = sum(e.get("event_type") == "completion_proposal" for e in task)
    facts["task_usage_missing_requests"] = max(0, facts["task_provider_requests"] - len(usage))
    try:
        facts["duration_seconds"] = (
            datetime.fromisoformat(result["finished_at"].replace("Z", "+00:00"))
            - datetime.fromisoformat(result["started_at"].replace("Z", "+00:00"))).total_seconds()
    except (KeyError, ValueError, TypeError):
        facts["duration_seconds"] = None
    progress = rows(root / "monitor/audit/progress.jsonl")
    facts["monitor_working_max_characters"] = max(
        [e.get("characters") or 0 for e in progress if e.get("event") == "dcec_state_mutation"]
        + [len((root / "monitor/private/working.md").read_text(encoding="utf-8"))])
    attempts = rows(root / "monitor/audit/request_attempts.jsonl")
    facts["monitor_attempt_outcomes"] = dict(Counter(e.get("outcome") for e in attempts))
    bridge = root / "bridge/evidence"
    release = json.loads((bridge / "verification_release.json").read_text(encoding="utf-8"))
    binding = json.loads((bridge / "trial_end_binding.json").read_text(encoding="utf-8"))
    facts["verification_release_decision"] = release.get("decision")
    facts["capture_boundary_hash_equal"] = (
        release.get("pre_verification_workspace_sha256") == release.get("boundary_workspace_sha256"))
    facts["trial_end_verification_released"] = binding.get("verification_released")
    dialogue = rows(root / "monitor/audit/dialogue.jsonl")
    controls = [e for e in dialogue if e.get("event") == "tool_call"
                and e.get("name") in ("wait", "intervene", "allow_complete")]
    facts["final_monitor_control_tool"] = controls[-1].get("name") if controls else None
    write(facts_path, facts)
    inputs = [(i, e) for i, e in enumerate(dialogue, 1) if e.get("event") == "model_input"]
    windows = [(i, e) for i, e in enumerate(dialogue, 1)
               if e.get("event") == "path_control_public_window"]
    gateway_requests = []
    with zipfile.ZipFile(root / "bridge/gateway_control_raw.zip") as archive:
        for name in archive.namelist():
            if not name.endswith(".pending.json"):
                continue
            pending = json.loads(archive.read(name))
            if pending.get("role") != "monitor":
                continue
            request_name = name.removesuffix(".pending.json") + ".request.json"
            payload = json.loads(archive.read(request_name))
            gateway_requests.append((pending["time_ns"], request_name, payload,
                                     "\n".join(strings(payload))))
    gateway_requests.sort()
    checks = []
    for (line, window), (time_ns, request_name, payload, request_text) in zip(windows, gateway_requests):
        content = window.get("content", "")
        checks.append({"window_dialogue_line": line, "gateway_request_archive_member": request_name,
                       "gateway_time_ns": time_ns,
                       "rendered_window_in_provider_ready_request": content in request_text,
                       "window_characters": len(content),
                       "source_lines": window.get("source_lines")})
    write(root / "REQUEST_ASSEMBLY_CHECK.json", {
        "condition": slot["condition"], "model_input_count": len(inputs),
        "monitor_gateway_request_count": len(gateway_requests),
        "path_window_count": len(windows), "paired_checks": checks,
        "note": "dialogue model_input is archived before request-local active-context injection; gateway request bodies are the provider-ready surface",
        "system_contract_all_requests": all(
            (SYSTEM_PROMPT if slot["condition"] == "PATH" else DCEC_SYSTEM_PROMPT)
            in "\n".join(strings(payload.get("system")))
            for _, _, payload, _ in gateway_requests),
        "working_guidance_all_path_requests": all(
            WORKING_GUIDANCE in text for _, _, _, text in gateway_requests)
            if slot["condition"] == "PATH" else None,
        "seven_atomic_tools_all_requests": all(
            len(payload.get("tools") or []) == 7 and
            not any(tool.get("name") in ("select_sources", "set_intent")
                    for tool in payload.get("tools") or [])
            for _, _, payload, _ in gateway_requests),
        "all_path_windows_visible": (all(c["rendered_window_in_provider_ready_request"] for c in checks)
                                     and len(windows) == len(gateway_requests))
                                    if slot["condition"] == "PATH" else (
                                        len(windows) == 0 and all(
                                            "Recent public Task events" not in text
                                            for _, _, _, text in gateway_requests)),
    })

    public = rows(root / "monitor/task_evidence/public_events.jsonl")
    index = json.loads((root / "EVENT_LOCATORS.json").read_text(encoding="utf-8"))
    for intervention in index["interventions"]:
        later = [(i, e) for i, e in enumerate(public, 1)
                 if isinstance(e.get("archived_at"), (int, float))
                 and e["archived_at"] > intervention["timestamp"]]
        intervention["next_public_events"] = [
            {"line": i, "archive_sequence": e.get("archive_sequence"),
             "task_turn": e.get("task_turn"), "boundary": e.get("boundary"),
             "tool_calls": len(e.get("tool_calls") or []),
             "tool_results": len(e.get("tool_results") or [])}
            for i, e in later[:5]]
        intervention["next_supervisor_workspace_observations"] = [
            {"dialogue_line": i, "review_id": e.get("review_id"), "name": e.get("name")}
            for i, e in enumerate(dialogue, 1)
            if i > intervention["dialogue_line"] and e.get("event") == "tool_call"
            and e.get("name") in ("file_read", "code_run")][:5]
    write(root / "EVENT_LOCATORS.json", index)
    return facts


def main():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    facts = [finalize(slot) for slot in plan["slots"]]
    write(PLAN_ROOT / "BLOCK_MECHANICAL_SUMMARY.json", {"records": facts})
    print(json.dumps({"records": len(facts),
                      "path_assembly_visible": [json.loads((RECORDS / f"{s['position']:02d}_{s['run_id']}"
                                               / "REQUEST_ASSEMBLY_CHECK.json").read_text())["all_path_windows_visible"]
                                                for s in plan["slots"]]}, indent=2))


if __name__ == "__main__":
    main()
