"""Fail-closed static diagnostic material and fake-provider controller.

No live provider, Task, Supervisor or native-evaluator entry exists here.
An actual tool-execution container must be certified separately.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import time

from method_discovery.curator_supervisor_convergence_v0.causal_reminder_turn30_20261007 import materialize as checkpoint
from method_discovery.curator_supervisor_convergence_v0.diagnostic_flex_preflight_v0_20261009 import check_workspace, freeze_inputs


HERE = Path(__file__).resolve().parent
ARCHIVE = freeze_inputs.ARCHIVE
PRE = freeze_inputs.HERE
SCENES = {"C01": ("progress_restraint", 120, 307),
          "C02": ("root_investigation", 161, 418)}
COMMON_NOTE = (
    "这是固定截止快照上的诊断。Task 不再推进；历史工具会话不代表仍有活动进程。"
    "可以调查允许的公开材料。wait、intervene、allow_complete 在此只记录诊断提议并结束当前诊断，"
    "不会等待 Task 新反馈、向 Task 投递消息或执行真实完成放行。"
)
LIMITS = {"provider_requests_including_retries": 12, "tool_calls_including_failures_and_polls": 48,
          "wall_seconds": 1200, "new_code_run_seconds": 60,
          "cumulative_tool_wait_seconds": 600}
ORDER = [("C01", 1, "B", "F"), ("C02", 1, "F", "B"),
         ("C01", 2, "F", "B"), ("C02", 2, "B", "F"),
         ("C01", 3, "B", "F"), ("C02", 3, "F", "B")]
CONTROL = {"wait", "intervene", "allow_complete"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def save_json(path: Path, value) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def request(scene: str, arm: str) -> dict:
    if scene not in SCENES or arm not in {"B", "F"}:
        raise ValueError("Unknown scene or condition")
    historical, _, _ = SCENES[scene]
    baseline = json.loads((PRE / f"{historical}_{arm}_REQUEST_DRAFT.json").read_text(encoding="utf-8"))
    result = copy.deepcopy(baseline)
    result["system"] += "\n\n" + COMMON_NOTE
    if any(key in result for key in ("temperature", "condition", "label")):
        raise RuntimeError("Unexpected model-visible request field")
    return result


def request_checks(scene: str) -> dict:
    historical = SCENES[scene][0]
    old_b = json.loads((PRE / f"{historical}_B_REQUEST_DRAFT.json").read_text(encoding="utf-8"))
    old_f = json.loads((PRE / f"{historical}_F_REQUEST_DRAFT.json").read_text(encoding="utf-8"))
    b, f = request(scene, "B"), request(scene, "F")
    if not (b["system"] == old_b["system"] + "\n\n" + COMMON_NOTE
            and f["system"] == old_f["system"] + "\n\n" + COMMON_NOTE):
        raise RuntimeError("Common static note differs")
    if {k: v for k, v in b.items() if k != "system"} != {
            k: v for k, v in f.items() if k != "system"}:
        raise RuntimeError("Non-system B/F difference")
    expected = b["system"]
    for before, after in freeze_inputs.REPLACEMENTS:
        if expected.count(before) != 1:
            raise RuntimeError("Frozen replacement missing")
        expected = expected.replace(before, after, 1)
    if f["system"] != expected or b["tools"] != old_b["tools"] or f["tools"] != old_f["tools"]:
        raise RuntimeError("Unexpected static condition change")
    return {"archived_B_sha256": sha(canonical(old_b)), "B_static_sha256": sha(canonical(b)),
            "F_static_sha256": sha(canonical(f)),
            "common_change": "append exact COMMON_NOTE to archived system; no other B change",
            "B_to_F_change": "exactly two frozen system paragraphs"}


def _prefix_jsonl(source: Path, destination: Path, count: int, key: str) -> dict:
    rows = source.read_bytes().splitlines(keepends=True)
    if len(rows) < count:
        raise RuntimeError(f"Truncated source: {source.name}")
    selected = rows[:count]
    for index, raw in enumerate(selected, 1):
        expected = f"public_events.jsonl#{index}" if key == "raw_event" else index
        if json.loads(raw)[key] != expected:
            raise RuntimeError(f"Noncontiguous {source.name} at {index}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"".join(selected))
    return {"source_sha256": sha(source.read_bytes()), "sha256": sha(destination.read_bytes()),
            "records": count, "cutoff_basis": key}


def _historic_outputs(dialogue: list[dict], private: Path, source: Path) -> dict:
    receipts: dict[str, list[dict]] = {}
    for event in dialogue:
        if event.get("event") == "tool_result" and isinstance(event.get("data"), dict):
            data = event["data"]
            if data.get("session_id") and "stdout" in data:
                receipts.setdefault(data["session_id"], []).append(data)
    included, unavailable = {}, {}
    for session, chain in receipts.items():
        last = chain[-1]
        archived = source / session / "output.log"
        visible = "".join(item["stdout"] for item in chain).encode("utf-8")
        complete = (last.get("status") in {"success", "error", "cancelled"}
                    and last.get("next_read") is None and last.get("unread_bytes") == 0)
        if complete and archived.is_file() and archived.read_bytes() == visible:
            target = private / "audit" / "commands" / session / "output.log"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(visible)
            included[session] = {"sha256": sha(visible), "bytes": len(visible),
                                 "last_status": last["status"], "receipt_count": len(chain),
                                 "basis": "concatenated cutoff receipts byte-equal archived output"}
        else:
            unavailable[session] = {"last_status": last.get("status"),
                                    "reason": "cutoff byte range or terminal lifecycle not proven"}
    return {"historical_completed_outputs": included, "unavailable_sessions": unavailable,
            "session_resume_rule": "Historical IDs are never rebound to new processes; unavailable returns explicit error."}


def materialize(scene: str, destination: Path) -> dict:
    """Make one fresh cutoff fixture. It is not an OS-isolated execution environment."""
    if scene not in SCENES or destination.exists():
        raise RuntimeError("Unknown scene or destination already exists")
    historical, cursor, dialogue_cutoff = SCENES[scene]
    public = ARCHIVE / "monitor/task_evidence/public_events.jsonl"
    events = [json.loads(line) for line in public.read_text(encoding="utf-8").splitlines()]
    if len(events) != 161 or sha(public.read_bytes()) != check_workspace.EXPECTED_PUBLIC_SHA:
        raise RuntimeError("Public archive identity mismatch")
    tree, rows = checkpoint.source_tree(checkpoint.IMAGE_APP, exclude_git=True)
    if tree != checkpoint.IMAGE_APP_TREE_SHA256 or len(rows) != 2468:
        raise RuntimeError("Clean task image mismatch")
    destination.mkdir(parents=True)
    app, evidence, private = destination / "app", destination / "task_evidence", destination / "monitor_private"
    shutil.copytree(checkpoint.IMAGE_APP, app)
    sidecar = app / checkpoint.ORIGINAL_TASK_SIDECAR
    sidecar.write_bytes(checkpoint.TASK.read_bytes())
    for event in events[:cursor]:
        if event["boundary"] == "post_tool_pre_next_llm":
            for call in event.get("tool_calls") or []:
                if call["name"] in {"file_write", "file_patch"}:
                    check_workspace.apply_file_mutation(app, event, call)
    actual_tree, actual_rows = checkpoint.source_tree(app, exclude_git=True)
    expected = json.loads((PRE / f"WORKSPACE_FILE_MANIFEST_CURSOR_{cursor}.json").read_text(encoding="utf-8"))
    if actual_rows != expected:
        raise RuntimeError("Cutoff workspace mismatch")
    evidence.mkdir()
    (evidence / "original_task.txt").write_bytes(checkpoint.TASK.read_bytes())
    public_meta = _prefix_jsonl(public, evidence / "public_events.jsonl", cursor, "archive_sequence")
    synopsis_meta = _prefix_jsonl(ARCHIVE / "monitor/task_evidence/synopsis.jsonl",
                                  evidence / "synopsis.jsonl", cursor, "raw_event")
    private.mkdir()
    book = ARCHIVE / "monitor/private/reference.md"
    if sha(book.read_bytes()) not in json.dumps(request(scene, "B")):
        raise RuntimeError("Archived Book does not match request-visible identity")
    (private / "reference.md").write_bytes(book.read_bytes())
    feedback = ARCHIVE / "monitor/private/delivery_feedback.jsonl"
    prior_feedback = [line for line in feedback.read_bytes().splitlines(keepends=True)
                      if (lambda row: row.get("kind") == "intervention" and
                          row.get("delivery_cursor", cursor + 1) <= cursor)(json.loads(line))]
    (private / "delivery_feedback.jsonl").write_bytes(b"".join(prior_feedback))
    dialogue = ARCHIVE / "monitor/audit/dialogue.jsonl"
    selected_dialogue = dialogue.read_bytes().splitlines(keepends=True)[:dialogue_cutoff]
    (private / "audit").mkdir(exist_ok=True)
    (private / "audit/dialogue.jsonl").write_bytes(b"".join(selected_dialogue))
    parsed_dialogue = [json.loads(line) for line in selected_dialogue]
    outputs = _historic_outputs(parsed_dialogue, private, ARCHIVE / "monitor/commands")
    manifest = {"scene_research_only": scene, "source_archive_commit": freeze_inputs.ARCHIVE_COMMIT,
                "workspace_tree_sha256": actual_tree, "ordinary_files": len(actual_rows),
                "public": public_meta, "synopsis": synopsis_meta,
                "book_sha256": sha(book.read_bytes()), "dialogue_records": dialogue_cutoff,
                "dialogue_prefix_sha256": sha(b"".join(selected_dialogue)),
                "delivery_feedback_sha256": sha(b"".join(prior_feedback)), "outputs": outputs,
                "tool_visible_roots": ["/app", "/logs/agent/monitor/task_evidence",
                                       "/logs/agent/monitor/monitor_private"],
                "isolation_certified": False}
    visible = []
    for root, basis in ((app, "clean image plus public mutations through cutoff"),
                        (evidence, "public task/event prefix through cutoff"),
                        (private, "private Book/feedback/dialogue/output receipt proven by cutoff")):
        for path in sorted(root.rglob("*")):
            if path.is_file():
                visible.append({"mount": root.name, "path": path.relative_to(root).as_posix(),
                                "sha256": sha(path.read_bytes()), "bytes": path.stat().st_size,
                                "cutoff_basis": basis})
    manifest["visible_files"] = visible
    save_json(destination / "RESEARCH_ONLY_MANIFEST.json", manifest)
    return manifest


class NoLiveProvider:
    def send(self, *_args, **_kwargs):
        raise RuntimeError("Live provider prohibited: static diagnostic is not authorized or isolated")


class FakeProvider:
    """Scripted responses only; no transport, credential or retry side effect."""
    def __init__(self, responses: list[list[dict]]):
        self.responses = iter(copy.deepcopy(responses))
        self.requests = []

    def send(self, request_payload: dict) -> list[dict]:
        self.requests.append(copy.deepcopy(request_payload))
        return next(self.responses)


def validate_args(tool: dict, arguments: dict) -> bool:
    if not isinstance(arguments, dict):
        return False
    schema = tool["input_schema"]
    if set(arguments) - set(schema["properties"]) or set(schema["required"]) - set(arguments):
        return False
    for name, value in arguments.items():
        spec = schema["properties"][name]
        kind = spec.get("type")
        if kind == "string" and not isinstance(value, str): return False
        if kind == "integer" and (type(value) is not int): return False
        if kind == "boolean" and type(value) is not bool: return False
        if kind == "number" and (type(value) not in (int, float)): return False
        if kind == "array" and not isinstance(value, list): return False
        if "enum" in spec and value not in spec["enum"]: return False
        if "minLength" in spec and len(value) < spec["minLength"]: return False
        if "maxLength" in spec and len(value) > spec["maxLength"]: return False
        if "minItems" in spec and len(value) < spec["minItems"]: return False
        if "maxItems" in spec and len(value) > spec["maxItems"]: return False
        if kind == "array" and any(not isinstance(item, str) or not 1 <= len(item) <= 200 for item in value):
            return False
        if "minimum" in spec and value < spec["minimum"]: return False
        if "maximum" in spec and value > spec["maximum"]: return False
    return True


class FakeDiagnostic:
    """Deterministic controller. Real tool and provider ports are deliberately absent."""
    def __init__(self, scene: str, backend=None):
        self.tools = {tool["name"]: tool for tool in request(scene, "B")["tools"]}
        self.backend = backend
        self.requests = 0
        self.tool_calls = 0
        self.terminal = None
        self.events = []
        self.wall_seconds = 0.0
        self.tool_wait_seconds = 0.0

    def failed_request_attempt(self, reason: str) -> str | None:
        if self.terminal is not None:
            raise RuntimeError("No provider retry after terminal disposition")
        self.requests += 1
        self.events.append({"kind": "failed_provider_attempt", "reason": reason})
        if self.requests >= LIMITS["provider_requests_including_retries"]:
            self.terminal = "undecided_budget"
        return self.terminal

    def attempt(self, calls: list[dict], *, elapsed_seconds=0.0, tool_wait_seconds=0.0) -> str | None:
        if self.terminal is not None:
            raise RuntimeError("No calls after terminal disposition")
        self.requests += 1
        self.wall_seconds += elapsed_seconds
        self.tool_wait_seconds += tool_wait_seconds
        self.events.append({"kind": "full_response", "calls": copy.deepcopy(calls)})
        if (self.requests > LIMITS["provider_requests_including_retries"] or
                self.wall_seconds >= LIMITS["wall_seconds"] or
                self.tool_wait_seconds >= LIMITS["cumulative_tool_wait_seconds"]):
            self.terminal = "undecided_budget"
            return self.terminal
        controls = [call for call in calls if call.get("name") in CONTROL]
        if len(controls) > 1:
            self.terminal = "protocol_invalid_conflicting_control"
            return self.terminal
        for index, call in enumerate(calls):
            self.tool_calls += 1
            if self.tool_calls > LIMITS["tool_calls_including_failures_and_polls"]:
                self.terminal = "undecided_budget"
                return self.terminal
            name, args = call.get("name"), call.get("arguments")
            tool = self.tools.get(name)
            if tool is None or not validate_args(tool, args):
                self.events.append({"kind": "tool_error", "index": index, "reason": "invalid_schema"})
                continue
            if name == "code_run" and args.get("timeout", 60) > LIMITS["new_code_run_seconds"]:
                self.events.append({"kind": "tool_error", "index": index, "reason": "static_command_timeout_cap"})
                continue
            if name in CONTROL:
                self.terminal = {"wait": "wait_proposal", "intervene": "intervention_proposal",
                                 "allow_complete": "release_proposal"}[name]
                self.events.append({"kind": "diagnostic_proposal_only", "index": index,
                                    "disposition": self.terminal})
                for later in range(index + 1, len(calls)):
                    self.events.append({"kind": "not_executed_after_proposal", "index": later})
                return self.terminal
            if self.backend is None:
                self.events.append({"kind": "fake_tool_receipt", "index": index, "name": name})
            else:
                started = time.monotonic()
                try:
                    receipt = self.backend.execute(name, args)
                    self.events.append({"kind": "tool_receipt", "index": index, "name": name,
                                        "receipt": receipt})
                except (OSError, RuntimeError, ValueError, TypeError) as exc:
                    self.events.append({"kind": "tool_error", "index": index, "name": name,
                                        "reason": type(exc).__name__})
                finally:
                    used = time.monotonic() - started
                    self.wall_seconds += used
                    self.tool_wait_seconds += used if name == "code_run" else 0
                if (self.wall_seconds >= LIMITS["wall_seconds"] or
                        self.tool_wait_seconds >= LIMITS["cumulative_tool_wait_seconds"]):
                    self.terminal = "undecided_budget"
                    return self.terminal
        return None
