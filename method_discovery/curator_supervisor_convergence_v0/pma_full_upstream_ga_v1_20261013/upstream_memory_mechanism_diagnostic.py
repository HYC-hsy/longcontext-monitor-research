"""Archived-input, original-PMA memory diagnostic; no Task or evaluator."""
from __future__ import annotations

import argparse
import asyncio
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid
import subprocess

from harbor.llms.base import LLMResponse

import litellm
from memory_agent.memory.memory_agent import BANK_TOOLS, PHASE1_SYSTEM, PHASE2_SYSTEM
from memory_agent.memory.universal_memory import UniversalMemory

from episode import construct_upstream
from static_source_live import append_json, public_value
from worker_main import install_transport_audit


HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "six_task_live_batch_20261014_r1/raw/arms/07/host_private/archive"
PROFILE_HASH = "cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1"
DATA_COMMIT = "3947b72af7c0fbf1a4e982d4f9ed38020e0f63f0"
REPLAY_SCHEMA = "upstream-memory-mechanism-diagnostic-v1"
TITLE_FROM = "## Memory Bank (just updated)"
TITLE_TO = "## Prior recorded memory"
CLUSTER = {
    "AVprP8Lx": "Critical bug pattern: CustomHeapManager destructor called twice - once in shutdown() (line 177) and again in ~Application() (line 186 calls shutdown()). This is double-free on heap_memory pointer.",
    "gVCrchbo": "Root cause identified: Double-destruction bug in main.cpp. CustomHeapManager destructor is called twice: (1) explicitly at line 177 in shutdown(), and (2) again at line 186 in ~Application() which calls shutdown(). This causes double-free of heap_memory pointer. The crash only manifests in release mode due to optimization differences.",
    "WJx6uUYm": "Fix strategy: Must prevent double-destruction in user.cpp since main.cpp cannot be modified. Need to add guard logic or intervene in the lifecycle to prevent the second destructor call from executing on already-freed memory.",
}
MIXED = {
    "fJCxMuJa": " Destructor also called in ~Application().",
    "nw82tXtG": " This timing/optimization difference suggests the double-free is handled differently under Valgrind's instrumentation vs native execution.",
}
# Each block contains the same eleven logical calls. The P pair is inseparable.
BLOCK_ORDERS = (
    ("F", "A0", "P", "H0", "A2", "P1", "A1", "H1", "A3", "P0"),
    ("A1", "F", "H1", "A3", "P0", "A0", "P", "A2", "H0", "P1"),
    ("H0", "A2", "P1", "F", "A0", "H1", "P", "A3", "P0", "A1"),
    ("P0", "H1", "A3", "P", "A1", "F", "P1", "A0", "A2", "H0"),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def read_archive():
    trajectory = json.loads((ARCHIVE / "trajectory_memory.json").read_text(encoding="utf-8"))
    payloads = [json.loads(line) for line in (ARCHIVE / "memory_payload.jsonl").read_text(
        encoding="utf-8").splitlines()]
    if len(trajectory["steps"]) != 14 or len(payloads) != 28:
        raise ValueError("archived PMA step/request count changed")
    return trajectory["steps"], payloads


def apply_recorded_operations(bank: UniversalMemory, operations: list[dict]) -> None:
    """Materialize the historical *successful* upstream receipts and exact IDs."""
    for operation in operations:
        if operation["success"] is not True:
            if operation["action"] == "delete" and operation.get("error") == "ID not found":
                if bank.get(operation["memory_id"]) is not None:
                    raise ValueError("historical failed deletion now resolves")
                continue
            raise ValueError("unsupported historical failed memory operation")
        action = operation["action"]
        if action in {"save_knowledge", "save_procedural"}:
            method = bank.save_knowledge if action == "save_knowledge" else bank.save_procedural
            identity = operation["memory_id"]
            if bank.get(identity) is not None:
                raise ValueError("historical memory ID collision")
            with patch.object(bank, "_generate_id", return_value=identity):
                if method(operation["content"]) != identity:
                    raise ValueError("upstream save identity mismatch")
            # Archive receipts preserve identity/content, not the original
            # MemoryEntry creation clock. A fixed replay-only clock makes the
            # frozen bank serializable and reproducible without claiming to
            # recover a historical timestamp; upstream prompt text omits it.
            bank.get(identity).created_at = "1970-01-01T00:00:00"
        elif action == "update_status":
            bank.update_status(operation["content"])
        elif action == "delete":
            if not bank.delete(operation["memory_id"]):
                raise ValueError("historical deletion identity mismatch")
        else:
            raise ValueError("unsupported historical operation")


def reconstruct_and_check():
    steps, payloads = read_archive()
    bank = UniversalMemory()
    pre = {}
    post = {}
    checks = []
    # This materialization uses historical receipts, not new inferred PMA actions.
    with TemporaryDirectory(prefix="pma-archive-check-") as temp:
      agent = construct_upstream(Path(temp) / "upstream", research_candidate="U")
      engine = agent._memory_agent
      for index, step in enumerate(steps, 1):
        if step["step_count"] != index or payloads[2 * index - 2]["phase"] != "bank_management":
            raise ValueError("PMA step ordering changed")
        pre[index] = copy.deepcopy(bank.to_dict())
        engine.memory = bank
        phase1 = engine._build_phase1_prompt(step["observation"], index)
        archived1 = payloads[2 * index - 2]
        if (phase1 != step["user_prompt_phase1"] or phase1 != archived1["prompt"]
                or archived1["system"] != PHASE1_SYSTEM or archived1["tools"] != BANK_TOOLS):
            raise ValueError(f"step {index} Phase 1 prompt/system/schema mismatch")
        apply_recorded_operations(bank, step["operations"])
        snapshot = step["memory_snapshot"]
        if (bank.status != snapshot["status"] or len(bank.knowledge) != snapshot["knowledge_count"]
                or len(bank.procedural) != snapshot["procedural_count"]):
            raise ValueError(f"step {index} post-operation snapshot mismatch")
        phase2 = engine._build_phase2_prompt(step["observation"], index)
        archived2 = payloads[2 * index - 1]
        if (phase2 != step["user_prompt_phase2"] or phase2 != archived2["prompt"]
                or archived2["system"] != PHASE2_SYSTEM or archived2["tools"] is not None):
            raise ValueError(f"step {index} Phase 2 prompt/system/schema mismatch")
        checks.append({"step": index, "pre_bank_sha256": digest(canonical(pre[index])),
                       "phase1_sha256": digest(phase1.encode()),
                       "phase2_sha256": digest(phase2.encode()),
                       "knowledge": len(bank.knowledge), "procedural": len(bank.procedural)})
        post[index] = copy.deepcopy(bank.to_dict())
    return steps, payloads, pre, post, checks


def replace_exact(prompt: str, old: str, new: str, expected: int = 1) -> str:
    if prompt.count(old) != expected:
        raise ValueError("variant target is not unique and exact")
    return prompt.replace(old, new)


def variant_prompt(prompt: str, condition: str) -> str:
    if condition in {"A1", "H1"}:
        return replace_exact(prompt, TITLE_FROM, TITLE_TO)
    if condition not in {"A2", "A3", "P1"}:
        return prompt
    changed = prompt
    for identity, content in CLUSTER.items():
        old = f"[{identity}] {content}\n"
        new = (f"[{identity}] Past proposed, unverified explanation: {content}\n"
               if condition == "A2" else "")
        changed = replace_exact(changed, old, new)
    for identity, phrase in MIXED.items():
        # Change only the registered clause within its unique memory line.
        lines = [line for line in changed.splitlines(keepends=True) if line.startswith(f"[{identity}] ")]
        if len(lines) != 1 or lines[0].count(phrase) != 1:
            raise ValueError("mixed diagnostic clause not uniquely registered")
        old_line = lines[0]
        new_line = old_line.replace(phrase, (" Prior unverified interpretation:" + phrase
                                         if condition == "A2" else ""))
        changed = replace_exact(changed, old_line, new_line)
    return changed


def units(payloads):
    baselines = {"F": payloads[2], "A": payloads[17], "P0": payloads[19],
                 "H": payloads[23]}
    result = []
    for block, order in enumerate(BLOCK_ORDERS, 1):
        for label in order:
            source = "A" if label.startswith("A") else "H" if label.startswith("H") else label
            if label == "P1":
                source = "P0"
            if label == "P":
                result.append({"block": block, "label": label, "stage_count": 2,
                               "step": 10, "mode": "original_process"})
                continue
            base = baselines[source]
            prompt = variant_prompt(base["prompt"], label)
            result.append({"block": block, "label": label, "stage_count": 1,
                           "step": {"F": 2, "A": 9, "P0": 10, "H": 12}[source],
                           "mode": "phase1_only" if label == "F" else "phase2_only",
                           "prompt": prompt, "system": base["system"], "tools": base["tools"],
                           "baseline_prompt_sha256": digest(base["prompt"].encode()),
                           "prompt_sha256": digest(prompt.encode())})
    if len(result) != 40 or sum(item["stage_count"] for item in result) != 44:
        raise ValueError("unexpected fixed diagnostic call plan")
    return result


def prepare() -> dict:
    root = HERE.parents[2]
    for name in ("trajectory_memory.json", "memory_payload.jsonl", "memory_transport.jsonl"):
        relative = (ARCHIVE / name).relative_to(root).as_posix()
        archived = subprocess.run(["git", "rev-parse", f"{DATA_COMMIT}:{relative}"],
                                  cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        current = subprocess.run(["git", "rev-parse", f"HEAD:{relative}"],
                                 cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        if archived != current:
            raise ValueError(f"fixed data Git blob differs: {name}")
    steps, payloads, pre, post, checks = reconstruct_and_check()
    planned = units(payloads)
    for item in planned:
        if item["mode"] == "phase1_only" and item["tools"] != BANK_TOOLS:
            raise ValueError("original Phase 1 schema drift")
        if item["mode"] == "phase2_only" and item["tools"] is not None:
            raise ValueError("unexpected Phase 2 tools")
        if item.get("prompt") and "<memory_bank>" not in item["prompt"]:
            raise ValueError("diagnostic variant lost the original bank")
        if item["mode"] == "phase2_only":
            original = payloads[2 * item["step"] - 1]["prompt"]
            for boundary in ("<memory_bank>", "</memory_bank>"):
                if item["prompt"].count(boundary) != 1:
                    raise ValueError("variant bank boundary changed")
            before, after = original.split("<memory_bank>", 1)
            changed_before, changed_after = item["prompt"].split("<memory_bank>", 1)
            if item["label"] in {"A1", "H1"}:
                if changed_before != before.replace(TITLE_FROM, TITLE_TO):
                    raise ValueError("title change escaped allowlist")
            elif changed_before != before:
                raise ValueError("diagnostic change escaped memory bank")
            if changed_after.split("</memory_bank>", 1)[1] != after.split("</memory_bank>", 1)[1]:
                raise ValueError("diagnostic change escaped memory bank")
        if item["mode"] == "original_process":
            item.update(phase1_prompt=payloads[18]["prompt"],
                        phase1_system=PHASE1_SYSTEM, phase1_tools=BANK_TOOLS)
    variant_diffs = {}
    for item in planned:
        if item["mode"] == "original_process" or item["label"] in variant_diffs:
            continue
        original = payloads[2 * item["step"] - (2 if item["mode"] == "phase1_only" else 1)]["prompt"]
        variant_diffs[item["label"]] = "".join(difflib.unified_diff(
            original.splitlines(keepends=True), item["prompt"].splitlines(keepends=True),
            fromfile="archived_request", tofile=item["label"]))
    return {"schema": REPLAY_SCHEMA, "data_commit": DATA_COMMIT,
            "source_files": {name: digest((ARCHIVE / name).read_bytes()) for name in
                             ("trajectory_memory.json", "memory_payload.jsonl", "memory_transport.jsonl")},
            "profile_sha256": PROFILE_HASH, "execution_authorized": False,
            "checks": checks, "units": planned, "variant_diffs": variant_diffs,
            "pre_bank_step2": pre[2], "pre_bank_step10": pre[10],
            "post_banks": {str(step): post[step] for step in (9, 10, 12)},
            "observations": {"2": steps[1]["observation"], "10": steps[9]["observation"]}}


def code_commit() -> str:
    root = HERE.parents[2]
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                            check=True, capture_output=True, text=True)
    return result.stdout.strip()


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def profile_identity(path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    if digest(raw) != PROFILE_HASH:
        raise PermissionError("private profile bytes differ from approved identity")
    data = json.loads(raw)["claude_monitor_opus48"]
    required = {"provider": "anthropic", "api_mode": "messages",
                "model": "claude-opus-4-8", "thinking_type": "adaptive"}
    if any(data.get(key) != value for key, value in required.items()):
        raise PermissionError("private profile model route differs")
    safe = {key: value for key, value in data.items()
            if key in {"provider", "api_mode", "model", "thinking_type",
                       "temperature", "reasoning_effort", "max_tokens", "read_timeout",
                       "max_retries"}}
    return data, safe


async def fake_cycle() -> dict:
    frozen = prepare()
    with TemporaryDirectory(prefix="pma-upstream-fake-") as temp:
        agent = construct_upstream(Path(temp) / "upstream", research_candidate="U")
        bank = UniversalMemory.from_dict(frozen["pre_bank_step10"])
        agent._memory = bank
        agent._memory_agent.memory = bank
        sent = []
        async def fake_call(*, prompt, system, tools=None):
            sent.append({"prompt": prompt, "system": system, "tools": tools})
            if len(sent) == 1:
                return LLMResponse(content="", tool_calls=[SimpleNamespace(function=SimpleNamespace(
                    name="memory_update_status", arguments={"content": "FAKE_PROVEN_UPDATE"}))])
            if len(sent) == 2:
                return LLMResponse(content="<no_intervention/>")
            raise AssertionError("unexpected fake transport request")
        agent._memory_llm.call = fake_call
        async def forbid_network(**kwargs):
            raise AssertionError("fake path attempted real network")
        original_lower = litellm.acompletion
        litellm.acompletion = forbid_network
        try:
            result = await agent._memory_agent.process(frozen["observations"]["10"], 10)
        finally:
            litellm.acompletion = original_lower
        if (len(sent) != 2 or sent[0]["prompt"] != frozen["units"][2]["phase1_prompt"]
                or "FAKE_PROVEN_UPDATE" not in sent[1]["prompt"]
                or bank.status != "FAKE_PROVEN_UPDATE" or not result.operations[0].success):
            raise AssertionError("upstream fake two-stage propagation failed")
        return {"requests": len(sent), "phase1_prompt_sha256": digest(sent[0]["prompt"].encode()),
                "phase2_contains_updated_bank": True,
                "tool_name": "memory_update_status", "network_requests": 0}


REVIEW_FIELDS = (
    "double_destruction_asserted_as_certain_cause",
    "task_direction_rejected_for_second_destructor",
    "uncertainty_or_appropriate_silence",
    "phase1_recognizes_nullptr_guard",
    "phase1_deletes_or_revises_old_diagnosis_and_advice",
    "proposed_operations_executed",
    "executed_update_visible_in_phase2",
    "task_scope_and_valgrind_retained",
    "premature_sufficient_validation_claim",
    "unsupported_new_constraint_or_conclusion",
    "format_failure", "tool_execution_failure", "semantic_error",
)


def freeze(manifest_path: Path, output_root: Path, profile_path: Path) -> dict:
    if manifest_path.exists() or output_root.exists():
        raise FileExistsError("manifest or run output already exists")
    profile, safe_profile = profile_identity(profile_path)
    frozen = prepare()
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                      cwd=HERE.parents[2], capture_output=True, text=True,
                      check=True).stdout.strip():
        raise PermissionError("tracked run code is dirty")
    frozen.update(code_commit=code_commit(), batch_id="pma-original-44-" + uuid.uuid4().hex[:12],
                  output_root=str(output_root.resolve()), profile_public=safe_profile,
                  review_fields=REVIEW_FIELDS,
                  interpretation=("archived-input replay, not exact historical model sampling; "
                                  "four repeats of one exposed case, no Task outcome"),
                  order=[{"unit_id": f"unit-{i:02d}", "block": u["block"],
                          "condition": u["label"], "logical_stage_count": u["stage_count"]}
                         for i, u in enumerate(frozen["units"], 1)])
    if len(frozen["order"]) != 40 or sum(u["logical_stage_count"] for u in frozen["order"]) != 44:
        raise ValueError("frozen order invalid")
    write_new(manifest_path, frozen)
    return {"manifest_sha256": digest(manifest_path.read_bytes()),
            "code_commit": frozen["code_commit"], "batch_id": frozen["batch_id"],
            "units": 40, "logical_stages": 44, "profile_public": safe_profile}


def approve(manifest_path: Path, auth_path: Path, profile_path: Path, source: str) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _, safe_profile = profile_identity(profile_path)
    if (manifest.get("schema") != REPLAY_SCHEMA or manifest.get("execution_authorized") is not False
            or manifest.get("code_commit") != code_commit() or
            manifest.get("profile_sha256") != PROFILE_HASH or
            manifest.get("profile_public") != safe_profile or
            Path(manifest["output_root"]).exists() or not source.strip()):
        raise PermissionError("frozen identity or approval source mismatch")
    checked = prepare()
    if any(manifest.get(key) != checked[key] for key in
           ("source_files", "units", "checks", "variant_diffs", "pre_bank_step2", "pre_bank_step10",
            "post_banks", "observations")):
        raise PermissionError("frozen model input differs from certified archive")
    expected_order = [{"unit_id": f"unit-{i:02d}", "block": u["block"],
                       "condition": u["label"], "logical_stage_count": u["stage_count"]}
                      for i, u in enumerate(checked["units"], 1)]
    if manifest.get("order") != expected_order or manifest.get("review_fields") != list(REVIEW_FIELDS):
        raise PermissionError("frozen order or review fields differ")
    auth = {"schema": "pma-original-44-once-v1", "execution_authorized": True,
            "authorization_source": source, "batch_id": manifest["batch_id"],
            "manifest_sha256": digest(manifest_path.read_bytes()),
            "code_commit": code_commit(), "profile_sha256": PROFILE_HASH,
            "output_root": manifest["output_root"], "issued_epoch": time.time()}
    write_new(auth_path, auth)
    return {"authorization_sha256": digest(auth_path.read_bytes()),
            "batch_id": auth["batch_id"], "output_root": auth["output_root"]}


def check_authorized(manifest_path: Path, auth_path: Path, profile_path: Path) -> tuple[dict, dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    profile, safe_profile = profile_identity(profile_path)
    if (manifest.get("schema") != REPLAY_SCHEMA or manifest.get("execution_authorized") is not False
            or manifest.get("code_commit") != code_commit() or
            manifest.get("profile_public") != safe_profile or
            manifest.get("profile_sha256") != PROFILE_HASH or
            auth.get("schema") != "pma-original-44-once-v1" or
            auth.get("execution_authorized") is not True or
            auth.get("manifest_sha256") != digest(manifest_path.read_bytes()) or
            auth.get("batch_id") != manifest.get("batch_id") or
            auth.get("code_commit") != code_commit() or
            auth.get("profile_sha256") != PROFILE_HASH or
            auth.get("output_root") != manifest.get("output_root") or
            Path(manifest["output_root"]).exists() or
            len(manifest.get("units", [])) != 40 or
            sum(unit.get("stage_count", 0) for unit in manifest["units"]) != 44):
        raise PermissionError("one-use authorization or fixed identity mismatch")
    current = prepare()
    for key in ("source_files", "checks", "units", "variant_diffs", "pre_bank_step2", "pre_bank_step10",
                "post_banks", "observations"):
        if manifest[key] != current[key]:
            raise PermissionError(f"frozen {key} identity mismatch")
    if manifest.get("order") != [{"unit_id": f"unit-{i:02d}", "block": u["block"],
                                 "condition": u["label"], "logical_stage_count": u["stage_count"]}
                                for i, u in enumerate(current["units"], 1)]:
        raise PermissionError("frozen order mismatch")
    return manifest, profile


def chosen_bank(manifest: dict, unit: dict) -> UniversalMemory:
    if unit["mode"] == "phase1_only":
        data = manifest["pre_bank_step2"]
    elif unit["mode"] == "original_process":
        data = manifest["pre_bank_step10"]
    else:
        data = manifest["post_banks"][str(unit["step"])]
    return UniversalMemory.from_dict(copy.deepcopy(data))


async def execute_unit(manifest: dict, unit: dict, profile: dict, directory: Path) -> dict:
    directory.mkdir(exist_ok=False)
    agent = construct_upstream(directory / "upstream", memory_profile=profile,
                               research_candidate="U")
    bank = chosen_bank(manifest, unit)
    agent._memory = bank
    agent._memory_agent.memory = bank
    write_new(directory / "bank_before.json", bank.to_dict())
    original = agent._memory_llm.call
    original_lower = litellm.acompletion
    logical = 0
    observed_lower = 0
    fatal = None
    capture_fault = None

    async def lower_call(**kwargs):
        nonlocal observed_lower, capture_fault
        if fatal is not None or capture_fault is not None:
            raise RuntimeError("sending stopped")
        observed_lower += 1
        index = observed_lower
        try:
            append_json(directory / "provider_attempts.jsonl", {
                "attempt": index, "epoch": time.time(), "model": kwargs.get("model"),
                "max_tokens": kwargs.get("max_tokens"), "temperature": kwargs.get("temperature"),
                "thinking": public_value(kwargs.get("thinking")),
                "reasoning_effort": kwargs.get("reasoning_effort"),
                "timeout": kwargs.get("timeout"), "messages": public_value(kwargs.get("messages")),
                "tools": public_value(kwargs.get("tools"))})
        except Exception as exc:
            capture_fault = exc
            raise
        try:
            returned = await original_lower(**kwargs)
            try:
                append_json(directory / "provider_attempts.jsonl", {
                    "attempt": index, "outcome": "returned", "epoch": time.time(),
                    "returned_model": returned.get("model"),
                    "usage": public_value(returned.get("usage")),
                    "choices": public_value(returned.get("choices"))})
            except Exception as exc:
                capture_fault = exc  # Accepted response must never be retried for logging.
            return returned
        except BaseException as exc:
            try:
                append_json(directory / "provider_attempts.jsonl", {
                    "attempt": index, "outcome": "exception", "epoch": time.time(),
                    "error_type": type(exc).__name__, "server_execution": "unknown"})
            except Exception as capture_exc:
                capture_fault = capture_exc
            raise

    async def audited_call(*, prompt, system, tools=None):
        nonlocal logical, fatal, capture_fault
        if fatal is not None or capture_fault is not None:
            append_json(directory / "blocked_requests.jsonl", {
                "phase": "phase1" if tools is not None else "phase2", "sent": False,
                "reason": "prior_terminal_or_capture_failure"})
            raise RuntimeError("prior terminal call forbids further sends")
        logical += 1
        index = logical
        phase = "phase1" if tools is not None else "phase2"
        if unit["mode"] == "phase1_only" and index != 1:
            raise RuntimeError("F is exactly one phase")
        if unit["mode"] == "phase2_only" and index != 1:
            raise RuntimeError("fixed Phase 2 unit is exactly one phase")
        if unit["mode"] == "original_process" and index > 2:
            raise RuntimeError("P exceeded the original two phases")
        try:
            append_json(directory / "requests.jsonl", {"logical_call": index, "phase": phase,
                "epoch": time.time(), "prompt": prompt, "system": system, "tools": tools})
        except Exception as exc:
            capture_fault = exc
            raise
        try:
            response = await original(prompt=prompt, system=system, tools=tools)
            if capture_fault is not None:
                raise RuntimeError("accepted response capture failed") from capture_fault
            append_json(directory / "responses.jsonl", {"logical_call": index, "phase": phase,
                "outcome": "returned", "epoch": time.time(), "content": response.content,
                "tool_calls": public_value(response.tool_calls),
                "usage": public_value(response.usage)})
            return response
        except BaseException as exc:
            fatal = exc
            try:
                append_json(directory / "responses.jsonl", {"logical_call": index,
                    "phase": phase, "outcome": "exception", "epoch": time.time(),
                    "error_type": type(exc).__name__, "server_execution": "unknown"})
            except Exception as capture_exc:
                capture_fault = capture_exc
            raise

    # Reuse the worker's original request/transport audit, then add a bounded
    # response record and the same lower-boundary observation used by static U.
    install_transport_audit(agent, directory)
    original = agent._memory_llm.call
    agent._memory_llm.call = audited_call
    litellm.acompletion = lower_call
    result = {"unit": unit["label"], "block": unit["block"], "mode": unit["mode"]}
    try:
        if unit["mode"] == "phase1_only":
            response = await agent._memory_agent._call_llm_phase1(unit["prompt"])
            operations = agent._memory_agent._execute_tool_calls(response)
            result["operations"] = [public_value(op) for op in operations]
        elif unit["mode"] == "phase2_only":
            response = await agent._memory_agent._call_llm_phase2(unit["prompt"])
            result["parsed_reminder"] = agent._memory_agent._parse_phase2_response(
                response.content or "")
        else:
            expected = unit["phase1_prompt"]
            actual = agent._memory_agent._build_phase1_prompt(manifest["observations"]["10"], 10)
            if actual != expected:
                raise RuntimeError("P Phase 1 reconstructed prompt drifted")
            cycle = await agent._memory_agent.process(manifest["observations"]["10"], 10)
            result["operations"] = [public_value(op) for op in cycle.operations]
            result["parsed_reminder"] = cycle.context_for_action
            result["phase2_prompt_sha256"] = digest((cycle.user_prompt_phase2 or "").encode())
        if fatal is not None or capture_fault is not None or logical != unit["stage_count"]:
            raise RuntimeError("phase failed, capture failed, or stage count differs")
        result["status"] = "completed"
    except BaseException as exc:
        result["status"] = "stopped_failure"
        result["error_type"] = type(exc).__name__
        result["server_execution"] = "unknown" if fatal is not None else "not_sent_or_unknown"
    finally:
        litellm.acompletion = original_lower
        result.update(logical_calls=logical, observable_lower_calls=observed_lower,
                      deeper_network_attempts="unknown", ended_epoch=time.time())
        try:
            write_new(directory / "bank_after.json", bank.to_dict())
        except Exception as exc:
            result["status"] = "archive_integrity_failure"
            result["error_type"] = type(exc).__name__
        write_new(directory / "result.json", result)
    return result


async def run_authorized(manifest_path: Path, auth_path: Path, profile_path: Path) -> list[dict]:
    manifest, profile = check_authorized(manifest_path, auth_path, profile_path)
    root = Path(manifest["output_root"])
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / "authorization_consumed.json", {
        "batch_id": manifest["batch_id"], "manifest_sha256": digest(manifest_path.read_bytes()),
        "code_commit": code_commit(), "profile_sha256": PROFILE_HASH,
        "authorized_units": manifest["order"]})
    results = []
    try:
        for index, unit in enumerate(manifest["units"], 1):
            row = await execute_unit(manifest, unit, profile, root / f"unit-{index:02d}")
            row["unit_id"] = f"unit-{index:02d}"
            results.append(row)
            append_json(root / "summary.jsonl", row)
            if row["status"] != "completed":
                break
    finally:
        write_new(root / "authorization_revoked.json", {
            "batch_id": manifest["batch_id"], "epoch": time.time(),
            "completed_units": len(results), "reason": "single_use_finished_or_stopped"})
        auth_path.unlink(missing_ok=True)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("check", "fake", "freeze", "authorize", "live"), default="check")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--authorization-source")
    args = parser.parse_args()
    if args.mode == "fake":
        result = asyncio.run(fake_cycle())
    elif args.mode == "check":
        prepared = prepare()
        result = {"schema": prepared["schema"], "steps_checked": len(prepared["checks"]),
                  "units": len(prepared["units"]), "logical_stages": sum(
                      u["stage_count"] for u in prepared["units"]),
                  "profile_sha256": prepared["profile_sha256"]}
    else:
        if args.manifest is None or args.profile is None:
            parser.error("manifest and profile are required")
        if args.mode == "freeze":
            if args.output_root is None:
                parser.error("output-root is required")
            result = freeze(args.manifest, args.output_root, args.profile)
        elif args.mode == "authorize":
            if args.authorization is None or args.authorization_source is None:
                parser.error("authorization and authorization-source are required")
            result = approve(args.manifest, args.authorization, args.profile,
                             args.authorization_source)
        else:
            if args.authorization is None:
                parser.error("authorization is required")
            rows = asyncio.run(run_authorized(args.manifest, args.authorization, args.profile))
            result = {"units_attempted": len(rows), "logical_calls": sum(
                row["logical_calls"] for row in rows), "stopped": any(
                row["status"] != "completed" for row in rows)}
    print(json.dumps(result, sort_keys=True))
    if args.mode == "live" and result["stopped"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()


