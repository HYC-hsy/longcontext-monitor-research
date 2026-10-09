"""Offline-only B/F input freeze from retained gateway requests.

This module has no provider transport or task-runner import. Its output is a
proposal, never an authorized model request.
"""

from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ARCHIVE_COMMIT = "8ff2675f92b979eb4747540e32ddba8e9fc0b2a9"
ARCHIVE = REPO / "method_discovery/curator_supervisor_convergence_v0/crs_rhr_rer_fyne_high_budget_20261007/archive/r1"
GATEWAY_ZIP = ARCHIVE / "bridge/gateway_control_raw.zip"
PROFILE = Path(r"E:\LongContext\long_context_bench\output\crs_rhr_rer_fyne_mechanism_gate\isolated_bundles\crs-rhr-rer-v0-fyne-bji-high-budget-r1\source\monitor_agent_core\models.local.json")
ASE = REPO / "GenericAgent-main/monitor_agent_core/ase_v0.py"

REPLACEMENTS = (
    (
        "When the Task Agent uses evidence to justify a consequential claim, supervise the measurement first. Treat tests, probes, builds, searches, logs, and source inspection as instruments, not verdicts. Before inspecting implementation in depth, identify the acceptance evidence the Agent is using and what it directly observes. Ask whether a concrete state violating a still-relevant task contract could produce the same observed result. Ground alternatives in the authoritative task, durable Task Book cognition, or public evidence; do not invent speculative defects. If a consequentially different violating state survives the measurement, the measurement does not support the stronger claim.",
        "When the Task Agent uses evidence to justify a consequential claim, identify the current evidence gap and choose the investigation path that can clarify it: trace the relevant implementation path or inspect the measurement and what it directly observes. Treat tests, probes, builds, searches, logs, and source inspection as instruments, not verdicts. Ask whether a concrete state violating a still-relevant task contract could produce the same observed result. Ground alternatives in the authoritative task, durable Task Book cognition, or public evidence; do not invent speculative defects. If a consequentially different violating state survives the measurement, the measurement does not support the stronger claim.",
    ),
    (
        "Your default is silence. Intervene when restoring relevant task cognition has control value. Prefer exposing the forgotten requirement, contradicted premise, learned distinction, or evidential limitation over prescribing implementation. The Task Agent owns implementation, debugging, test construction, and experimentation.",
        "Your default is silence. Intervene when restoring relevant task cognition has control value. When public evidence supports it, you may give a concrete diagnosis and a useful next investigation suggestion; keep the relevant task conflict and evidential basis clear, without taking ownership of implementation. The Task Agent owns implementation, debugging, test construction, and experimentation.",
    ),
)
SCENES = {
    "progress_restraint": {"dialogue_line": 308, "request_entry": "f7c3cd06a18e4a2db685c1ec6ea26dc6.request.json", "public_cutoff": 120},
    "root_investigation": {"dialogue_line": 419, "request_entry": "1175ad67aa2e4bddaeff9476f4064cc6.request.json", "public_cutoff": 161},
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def git_blob_matches(path: Path) -> bool:
    relative = path.relative_to(REPO).as_posix()
    recorded = subprocess.check_output(["git", "rev-parse", f"{ARCHIVE_COMMIT}:{relative}"], cwd=REPO).strip()
    current = subprocess.check_output(["git", "hash-object", str(path)], cwd=REPO).strip()
    return recorded == current


def ase_prompt() -> str:
    module = ast.parse(ASE.read_text(encoding="utf-8"))
    return next(ast.literal_eval(node.value) for node in module.body
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == "SYSTEM_PROMPT" for target in node.targets))


def main() -> None:
    if not GATEWAY_ZIP.is_file() or not PROFILE.is_file() or not git_blob_matches(GATEWAY_ZIP):
        raise RuntimeError("Gateway source/profile missing or archive commit mismatch")
    dialogue_path = ARCHIVE / "monitor/audit/dialogue.jsonl"
    if not git_blob_matches(dialogue_path):
        raise RuntimeError("Dialogue differs from archive commit")
    dialogue = [json.loads(line) for line in dialogue_path.open(encoding="utf-8")]
    with zipfile.ZipFile(GATEWAY_ZIP) as gateway:
        monitor_entries = [name for name in gateway.namelist() if name.endswith(".request.json")
                           and json.loads(gateway.read(name.replace(".request.json", ".permit.json")))["role"] == "monitor"]
        task_entries = [name for name in gateway.namelist() if name.endswith(".request.json")
                        and json.loads(gateway.read(name.replace(".request.json", ".permit.json")))["role"] == "task"]
        monitor_entries.sort(key=lambda name: json.loads(gateway.read(
            name.replace(".request.json", ".permit.json")))["time_ns"])
        if len(monitor_entries) != 56 or len(task_entries) != 83:
            raise RuntimeError("Gateway role request counts differ")
        first_prompt = None
        identity = {}
        for scene, settings in SCENES.items():
            line = settings["dialogue_line"]
            event = dialogue[line - 1]
            if event.get("event") != "model_input":
                raise RuntimeError(f"Scene {scene} is not a model input")
            index = sum(row.get("event") == "model_input" for row in dialogue[:line]) - 1
            entry = monitor_entries[index]
            if entry != settings["request_entry"]:
                raise RuntimeError(f"Scene {scene} gateway sequencing differs")
            raw = gateway.read(entry)
            request = json.loads(raw)
            permit = json.loads(gateway.read(entry.replace(".request.json", ".permit.json")))
            if not (event["timestamp"] < permit["time_ns"] / 1e9 < event["timestamp"] + 3):
                raise RuntimeError(f"Scene {scene} gateway request time differs")
            context = next(row for row in dialogue if row.get("event") == "review_context"
                           and row.get("review_id") == event["review_id"])
            if request["system"] != context["system_prompt"]:
                raise RuntimeError(f"Scene {scene} gateway system differs from review")
            for item in event["messages"]:
                if item["role"] == "system":
                    if item["content"] != request["system"]:
                        raise RuntimeError(f"Scene {scene} system delta differs")
                    continue
                if not any(item["content"] in block.get("text", "") for message in request["messages"]
                           if message["role"] == item["role"] for block in message["content"]
                           if isinstance(block, dict)):
                    raise RuntimeError(f"Scene {scene} incremental input absent from complete request")
            if len(request["tools"]) != 7 or request["model"] != "claude-opus-4-8":
                raise RuntimeError(f"Scene {scene} tools/model differ")
            if first_prompt is None:
                first_prompt = request["system"]
            elif request["system"] != first_prompt:
                raise RuntimeError("Scenes have different B system text")
            write_json(HERE / f"{scene}_B_REQUEST_DRAFT.json", request)
            identity[scene] = {"dialogue_line": line, "review_id": event["review_id"],
                               "public_cutoff": settings["public_cutoff"],
                               "gateway_entry": entry, "gateway_raw_sha256": digest(raw),
                               "B_request_canonical_sha256": digest(canonical(request)),
                               "model": request["model"], "message_count": len(request["messages"]),
                               "tool_names": [tool["name"] for tool in request["tools"]],
                               "request_time_ns": permit["time_ns"]}
            settings["_request"] = request
    if first_prompt is None or not first_prompt.startswith(ase_prompt()):
        raise RuntimeError("Recorded B prompt differs from ASE source")
    suffix = first_prompt[len(ase_prompt()):]
    if suffix != "\n\nUse the ordinary tools to observe and control the public task. A submitted local intervention ends this review so the Task can respond; the next wake provides new public feedback to assess. Use wait to finish without intervention, or allow_complete only for a current justified root handoff. Delivery feedback remains available at monitor/delivery_feedback.jsonl.":
        raise RuntimeError("Recorded review guidance suffix differs")
    after = first_prompt
    for before_text, after_text in REPLACEMENTS:
        if after.count(before_text) != 1:
            raise RuntimeError("Replacement original is not unique")
        after = after.replace(before_text, after_text, 1)
    (HERE / "B_SYSTEM.txt").write_bytes(first_prompt.encode("utf-8"))
    (HERE / "F_SYSTEM.txt").write_bytes(after.encode("utf-8"))
    diff = "".join(difflib.unified_diff(first_prompt.splitlines(keepends=True),
                                        after.splitlines(keepends=True), n=0,
                                        fromfile="B_SYSTEM.txt", tofile="F_SYSTEM.txt"))
    (HERE / "PROMPT_DIFF.patch").write_bytes(diff.encode("utf-8"))
    for scene, settings in SCENES.items():
        treatment = copy.deepcopy(settings.pop("_request"))
        treatment["system"] = after
        write_json(HERE / f"{scene}_F_REQUEST_DRAFT.json", treatment)
        baseline = json.loads((HERE / f"{scene}_B_REQUEST_DRAFT.json").read_text(encoding="utf-8"))
        if {key: value for key, value in baseline.items() if key != "system"} != {
                key: value for key, value in treatment.items() if key != "system"}:
            raise RuntimeError("Non-system request difference")
        identity[scene]["F_request_canonical_sha256"] = digest(canonical(treatment))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    allowed = ("model", "provider", "max_tokens", "temperature", "reasoning_effort", "thinking_type",
               "context_win", "monitor_adaptive_supervisory_environment", "monitor_contrastive_release_state",
               "monitor_receding_horizon_release", "monitor_root_epistemic_reestimation",
               "monitor_ase_meta_regulation")
    write_json(HERE / "SOURCE_IDENTITY.json", {"archive_commit": ARCHIVE_COMMIT,
        "gateway_zip_sha256": digest(GATEWAY_ZIP.read_bytes()),
        "dialogue_sha256": digest(dialogue_path.read_bytes()),
        "private_profile_file_sha256": digest(PROFILE.read_bytes()),
        "sanitized_supervisor_profile": {key: profile[key] for key in allowed},
        "ase_source_sha256": digest(ASE.read_bytes()), "ase_system_sha256": digest(ase_prompt().encode()),
        "B_system_sha256": digest(first_prompt.encode()), "F_system_sha256": digest(after.encode()),
        "scene_requests": identity, "condition_names_model_visible": False,
        "provider_calls_this_preflight": 0})
    print(json.dumps({"B_system_sha256": digest(first_prompt.encode()),
                      "F_system_sha256": digest(after.encode()),
                      "scene_requests": identity}, ensure_ascii=False))


if __name__ == "__main__":
    main()
