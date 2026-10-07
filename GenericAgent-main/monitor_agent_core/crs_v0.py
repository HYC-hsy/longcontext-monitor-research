"""Review-local contrastive root release; mechanical provenance, no verdicts."""

from __future__ import annotations

import hashlib
import json
import re

from .ase_v0 import ReconsiderationBoundary


_PUBLIC = re.compile(r"task/public_events\.jsonl#([1-9][0-9]*)\Z")
_DIALOGUE = re.compile(r"monitor/audit/dialogue\.jsonl#([1-9][0-9]*)\Z")
_ORIGINAL = re.compile(r"task/original_task\.txt(?: line ([1-9][0-9]*)| lines ([1-9][0-9]*)-([1-9][0-9]*))?\Z")
_COMMAND_OUTPUT = re.compile(r"monitor/audit/commands/([^/]+)/output\.log\Z")
_HANDLE = re.compile(r"obs:(?:read|code):[0-9a-f]{24}\Z")
_FIELDS = {"release_blocking_state", "grounding", "ground_refs", "exclusion_reason", "observation_refs"}
_MAX_TEXT = {"release_blocking_state": 1200, "grounding": 1200, "exclusion_reason": 1600}
CRS_PUBLIC_RESULT_EXCERPT_CHARS = 640
CRS_SURFACE_MAX_CHARS = 16000
CRS_CITABLE_MAX_CHARS = 4000
RHR_SURFACE_MAX_CHARS = 4000


def _dialogue_receipts(workspace, review_id=None):
    """Return only actual paired file_read/code_run tool-result receipts."""
    path = workspace.private_root / "audit/dialogue.jsonl"
    if not path.is_file():
        return []
    calls = {}
    found = []
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            key = (row.get("review_id"), row.get("tool_id"))
            if row.get("event") == "tool_call" and row.get("name") in {"file_read", "code_run"}:
                calls[key] = row
            elif row.get("event") == "tool_result" and key in calls and isinstance(row.get("data"), dict):
                if review_id is not None and row.get("review_id") != review_id:
                    continue
                locator = f"monitor/audit/dialogue.jsonl#{number}"
                kind = "read" if calls[key]["name"] == "file_read" else "code"
                handle = f"obs:{kind}:{hashlib.sha256(locator.encode('utf-8')).hexdigest()[:24]}"
                found.append((handle, locator, calls[key], row))
    return found


def _allowed_formats(workspace, review_id):
    handles = [item[0] for item in _dialogue_receipts(workspace, review_id)[-5:]]
    return ("ground_refs: task/original_task.txt [line N|lines N-M], monitor/reference.md, "
            "task/public_events.jsonl#cursor. observation_refs: an exact CRS observation handle "
            "shown in active context, a uniquely resolvable monitor/audit/commands/<session>/output.log, "
            "or task/public_events.jsonl#cursor containing tool results. "
            f"Current citable handles: {', '.join(handles) if handles else 'none'}")


def _resolve_observation_alias(ref, workspace):
    if _HANDLE.fullmatch(ref):
        matches = [item for item in _dialogue_receipts(workspace) if item[0] == ref]
    elif _COMMAND_OUTPUT.fullmatch(ref):
        matches = [item for item in _dialogue_receipts(workspace)
                   if item[2].get("name") == "code_run" and
                   item[3]["data"].get("output_path") == ref]
    else:
        return None
    if len(matches) != 1:
        raise ValueError("observation identity does not resolve to exactly one actual tool receipt")
    return matches[0][1]


def _row(path, index):
    if not path.is_file():
        raise ValueError("Referenced source does not exist")
    with path.open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if number == index:
                return json.loads(line)
    raise ValueError("Referenced source line does not exist")


def _reference(ref, workspace, observation):
    if not isinstance(ref, str) or len(ref) > 200:
        raise ValueError("Contrast locator must be a bounded string")
    original = _ORIGINAL.fullmatch(ref)
    if not observation and (original or ref == "monitor/reference.md"):
        locator = "task/original_task.txt" if original else ref
        path = workspace.resolve_read(locator)
        result = {"locator": locator, "submitted_ref": ref,
                  "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if original and (original.group(1) or original.group(2)):
            first = int(original.group(1) or original.group(2))
            last = int(original.group(1) or original.group(3))
            if last < first or last > len(path.read_text(encoding="utf-8").splitlines()):
                raise ValueError("requested original-task line range does not exist")
            result["line_start"], result["line_end"] = first, last
        return result
    if observation:
        alias = _resolve_observation_alias(ref, workspace)
        if alias is not None:
            resolved = _reference(alias, workspace, True)
            resolved["submitted_ref"] = ref
            return resolved
    public = _PUBLIC.fullmatch(ref)
    if public:
        cursor = int(public.group(1))
        event = _row(workspace.resolve_read("task/public_events.jsonl"), cursor)
        if not isinstance(event, dict) or event.get("archive_sequence") != cursor:
            raise ValueError("Public locator must match an archived event cursor")
        if observation:
            results = event.get("tool_results")
            if not isinstance(results, list) or not results:
                raise ValueError("source exists but is not an observation result (no tool results)")
            raw_results = json.dumps(results, ensure_ascii=False, separators=(",", ":"))
            return {"locator": ref, "source": "task_tool_result",
                    "task_turn": event.get("task_turn"),
                    "archive_sequence": event.get("archive_sequence"),
                    "tool_result_count": len(results),
                    "tool_result_sha256": hashlib.sha256(json.dumps(
                        results, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
                    "tool_results_json_excerpt": raw_results[:CRS_PUBLIC_RESULT_EXCERPT_CHARS],
                    "tool_results_json_characters": len(raw_results),
                    "tool_results_excerpt_truncated": len(raw_results) > CRS_PUBLIC_RESULT_EXCERPT_CHARS}
        return {"locator": ref, "source": "public_event",
                "task_turn": event.get("task_turn"),
                "archive_sequence": event.get("archive_sequence")}
    dialogue = _DIALOGUE.fullmatch(ref)
    if observation and dialogue:
        path = workspace.private_root / "audit/dialogue.jsonl"
        index = int(dialogue.group(1))
        receipt = _row(path, index)
        if receipt.get("event") != "tool_result" or not receipt.get("tool_id"):
            raise ValueError("Supervisor observation locator must identify a tool result")
        call = None
        with path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if number >= index:
                    break
                candidate = json.loads(line)
                if (candidate.get("event") == "tool_call" and
                        candidate.get("tool_id") == receipt["tool_id"] and
                        candidate.get("review_id") == receipt.get("review_id")):
                    call = candidate
        if call is None or call.get("name") not in {"file_read", "code_run"}:
            raise ValueError("Observation has no matching file_read/code_run call")
        data = receipt.get("data")
        if not isinstance(data, dict):
            raise ValueError("Observation receipt has no structured result")
        arguments = call.get("arguments")
        try:
            requested = json.loads(arguments) if isinstance(arguments, str) else arguments
        except (TypeError, ValueError):
            requested = {}
        if not isinstance(requested, dict):
            requested = {}
        fields = ("path", "start", "lines", "offset", "total_lines", "sha256", "truncated",
                  "more_lines_after_range",
                  "status", "session_id", "exit_code", "error_type", "cancelled",
                  "running", "output_path")
        result = {"locator": ref, "source": "supervisor_tool_result",
                "tool_name": call["name"], "tool_id": receipt["tool_id"],
                "receipt_sha256": hashlib.sha256(json.dumps(
                    data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
                "lifecycle": {key: data[key] for key in fields if key in data}}
        if call["name"] == "file_read":
            result["requested_range"] = {
                key: requested[key] for key in ("path", "start", "count", "tail", "offset", "max_chars")
                if key in requested}
        return result
    raise ValueError("Contrast locator is not an allowed source for this field")


def validate_contrast(value, workspace, review_id=None):
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("allow_complete requires exactly these flat fields: " + ", ".join(sorted(_FIELDS)))
    for field, maximum in _MAX_TEXT.items():
        text = value[field]
        if not isinstance(text, str) or not text.strip() or len(text) > maximum:
            raise ValueError(f"{field} must be non-empty and at most {maximum} characters")
    provenance = {}
    for field, observation in (("ground_refs", False), ("observation_refs", True)):
        refs = value[field]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 4 or len(set(map(str, refs))) != len(refs):
            raise ValueError(f"{field} requires 1–4 distinct locators. " +
                             _allowed_formats(workspace, review_id))
        provenance[field] = []
        for index, ref in enumerate(refs):
            try:
                provenance[field].append(_reference(ref, workspace, observation))
            except (ValueError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"{field}[{index}] submitted_ref={str(ref)[:200]!r} "
                                 f"cannot be resolved: {exc}. " +
                                 _allowed_formats(workspace, review_id)) from exc
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return canonical, hashlib.sha256(canonical.encode("utf-8")).hexdigest(), provenance


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _display(value, key=""):
    """Bound only transport text, never the provenance used for state identity."""
    if isinstance(value, dict):
        return {name: _display(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_display(item, key) for item in value]
    if isinstance(value, str):
        limit = CRS_PUBLIC_RESULT_EXCERPT_CHARS if key == "tool_results_json_excerpt" else 240
        return value if len(value) <= limit else value[:limit] + f" [truncated; {len(value)} source chars]"
    return value


def _surface(active):
    surface = (
        "Contrastive Release State — your own proposed whole-task release cognition, "
        "not task truth or runtime verification. Release has not executed. "
        "You may investigate, intervene, or revise this contrast. To release on it, "
        "submit this same exact contrast again after seeing it in this model request.\n"
        "mechanical provenance only; no adequacy/support/verdict is supplied by runtime.\n"
        f"contrast_sha256={active['sha256']} provenance_sha256={active['provenance_sha256']} "
        f"state_digest={active['state_digest']}\n"
        "Model-authored contrast (flat allow_complete arguments):\n" + active["canonical"] + "\n"
        "Resolved mechanical provenance for cited sources:\n" +
        _canonical(_display(active["provenance"]))
    )
    if len(surface) > CRS_SURFACE_MAX_CHARS:
        raise ValueError(f"CRS surface exceeds {CRS_SURFACE_MAX_CHARS} characters; shorten contrast or references")
    return surface


def _handoff_identity(handoff):
    return {key: handoff.get(key) for key in ("request_id", "generation", "cursor")}


def _task_book_sha256(workspace):
    return hashlib.sha256(workspace.resolve_read("monitor/reference.md").read_bytes()).hexdigest()


def _root_horizon_digest(handoff, task_book_sha256, focal_state_digest):
    source = (_canonical(handoff) + "\n" + task_book_sha256 + "\n" + focal_state_digest)
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _rhr_surface(active):
    surface = (
        "Root Horizon Reset — control phase only; not task truth or runtime verification.\n"
        "Whole-task release has not executed. The prior focal CRS is one release-blocking "
        "cognition you selected; runtime has not judged it correct, sufficient, or resolved. "
        "Repeating one focal CRS does not by itself support unrelated parts of the whole task. "
        "The full public task, Task Book, and ordinary root context are available in this request. "
        "Reconsider the whole mission: investigate, intervene, submit a different grounded "
        "release-blocking state, or, if no other currently grounded action-changing state "
        "is identifiable, resubmit the prior exact CRS in a later model response to release.\n"
        f"root_horizon_digest={active['root_horizon_digest']} "
        f"prior_focal_state_digest={active['prior_focal']['state_digest']} "
        f"task_book_sha256={active['task_book_sha256']} "
        f"handoff={_canonical(active['handoff'])}\n"
        "Prior release_blocking_state excerpt: " +
        json.loads(active['prior_focal']['canonical'])['release_blocking_state'][:1200]
    )
    if len(surface) > RHR_SURFACE_MAX_CHARS:
        raise ValueError("Root Horizon Reset surface exceeds mechanical transport bound")
    return surface


class ContrastiveReleaseBoundary(ReconsiderationBoundary):
    """Extends ASE reconsideration only for root allow_complete."""

    def __init__(self, audit, visible_context, *, receding_horizon=False):
        super().__init__(audit, visible_context)
        self.receding_horizon = receding_horizon
        self.root_contrast = None
        self.root_reorientation = None

    def begin_review(self, review_id):
        super().begin_review(review_id)
        self.root_contrast = None
        self.root_reorientation = None

    def _enter_root_reorientation(self, focal, workspace):
        book_sha = _task_book_sha256(workspace)
        active = {"prior_focal": focal, "handoff": focal["handoff"],
                  "task_book_sha256": book_sha,
                  "root_horizon_digest": _root_horizon_digest(
                      focal["handoff"], book_sha, focal["state_digest"]),
                  "entered_turn": self.model_turn, "surfaced": False,
                  "surfaced_request_id": None}
        _rhr_surface(active)
        self.root_contrast = None
        self.root_reorientation = active
        self.audit("rhr_entered", prior_focal_state_digest=focal["state_digest"],
                   handoff=focal["handoff"], task_book_sha256=book_sha,
                   root_horizon_digest=active["root_horizon_digest"], model_turn=self.model_turn)
        return active

    def _refresh_root_reorientation(self, workspace):
        active = self.root_reorientation
        if active is None:
            return None
        book_sha = _task_book_sha256(workspace)
        if book_sha != active["task_book_sha256"]:
            old_digest = active["root_horizon_digest"]
            active["task_book_sha256"] = book_sha
            active["root_horizon_digest"] = _root_horizon_digest(
                active["handoff"], book_sha, active["prior_focal"]["state_digest"])
            active["entered_turn"] = self.model_turn
            active["surfaced"] = False
            active["surfaced_request_id"] = None
            self.audit("rhr_reentered", old_root_horizon_digest=old_digest,
                       new_root_horizon_digest=active["root_horizon_digest"],
                       reason="task_book_changed", handoff=active["handoff"])
        return active

    def render_citable_observations(self, workspace, review_id):
        receipts = _dialogue_receipts(workspace, review_id)[-5:]
        if not receipts:
            return None
        lines = ["CRS-citable observation receipts — mechanical provenance only; "
                 "no adequacy/support/verdict is supplied by runtime. Copy an exact obs: handle "
                 "as an observation_ref. Only returned observations from this root review appear here."]
        for handle, locator, call, receipt in receipts:
            data = receipt["data"]
            identity = {key: data[key] for key in
                        ("path", "start", "lines", "sha256", "truncated", "output_path",
                         "session_id", "status", "exit_code", "cancelled", "running", "error_type")
                        if key in data}
            line = f"{handle} -> {locator}; tool={call['name']}; " + _canonical(_display(identity))
            if len(line) > 680:
                line = line[:680] + " [render truncated]"
            lines.append(line)
        surface = "\n".join(lines)
        if len(surface) > CRS_CITABLE_MAX_CHARS:
            raise ValueError("CRS citable receipt surface exceeds mechanical transport bound")
        self.audit("crs_citable_observations_prepared", citable_review_id=review_id,
                   handles=[item[0] for item in receipts],
                   surface_sha256=hashlib.sha256(surface.encode("utf-8")).hexdigest())
        return surface

    def root_release(self, contrast, handoff, workspace):
        canonical, digest, provenance = validate_contrast(contrast, workspace, self.review_id)
        provenance_text = _canonical(provenance)
        provenance_digest = hashlib.sha256(provenance_text.encode("utf-8")).hexdigest()
        state_digest = hashlib.sha256((canonical + "\n" + provenance_text).encode("utf-8")).hexdigest()
        identity = _handoff_identity(handoff)
        prior = self.root_contrast
        proposed = {"canonical": canonical, "sha256": digest,
                    "provenance_sha256": provenance_digest, "state_digest": state_digest,
                    "handoff": identity, "proposed_turn": self.model_turn,
                    "surfaced": False, "surfaced_request_id": None,
                    "provenance": provenance}
        _surface(proposed)  # Fail before changing state if transport cannot be bounded.
        if prior is not None and prior["handoff"] != identity:
            self._clear_root("stale_handoff")
            prior = None
        reset = self.root_reorientation
        if reset is not None and reset["handoff"] != identity:
            self._clear_root("stale_handoff")
            reset = None
        self.audit("crs_release_attempted", contrast_sha256=digest,
                   provenance_sha256=provenance_digest, state_digest=state_digest, handoff=identity,
                   ground_refs=provenance["ground_refs"],
                   observation_refs=provenance["observation_refs"], model_turn=self.model_turn)
        if reset is not None:
            focal = reset["prior_focal"]
            if focal["canonical"] != canonical or focal["state_digest"] != state_digest:
                self.audit("rhr_new_focal_selected",
                           prior_focal_state_digest=focal["state_digest"],
                           new_focal_state_digest=state_digest, handoff=identity)
                self._clear_root("new_focal_selected")
                prior = None
            else:
                reset = self._refresh_root_reorientation(workspace)
                if (reset["surfaced"] and self.model_turn is not None
                        and self.model_turn > reset["entered_turn"]):
                    self.audit("rhr_final_release_confirmed",
                               root_horizon_digest=reset["root_horizon_digest"],
                               prior_focal_state_digest=focal["state_digest"],
                               final_focal_state_digest=state_digest,
                               surfaced_request_id=reset["surfaced_request_id"],
                               model_turn=self.model_turn, handoff=identity)
                    self.root_reorientation = None
                    return None
                return {"status": "release_not_executed",
                        "root_horizon_digest": reset["root_horizon_digest"],
                        "message": "Whole-task release has not executed. Root Horizon Reset must appear in a later model request before final confirmation."}
        if (prior is not None and prior["canonical"] == canonical
                and prior["state_digest"] == state_digest and prior["surfaced"]
                and self.model_turn is not None and self.model_turn > prior["proposed_turn"]):
            self.audit("crs_confirmed", contrast_sha256=digest,
                       provenance_sha256=provenance_digest, state_digest=state_digest, handoff=identity,
                       surfaced_request_id=prior["surfaced_request_id"], model_turn=self.model_turn)
            if self.receding_horizon:
                reset = self._enter_root_reorientation(prior, workspace)
                return {"status": "release_not_executed",
                        "root_horizon_digest": reset["root_horizon_digest"],
                        "message": "Focal CRS reaffirmed; whole-task release has not executed. Root Horizon Reset must appear in a later model request."}
            self.root_contrast = None
            return None
        if prior is not None and prior["state_digest"] != state_digest:
            self._clear_root("revised")
            self.audit("crs_revised", old_sha256=prior["sha256"], new_sha256=digest,
                       old_state_digest=prior["state_digest"], new_state_digest=state_digest,
                       same_contrast=prior["canonical"] == canonical, handoff=identity)
        if prior is None or prior["state_digest"] != state_digest:
            self.root_contrast = proposed
            self.audit("crs_proposed", contrast_sha256=digest,
                       provenance_sha256=provenance_digest, state_digest=state_digest, handoff=identity,
                       canonical_contrast=canonical, model_turn=self.model_turn,
                       ground_refs=provenance["ground_refs"],
                       observation_refs=provenance["observation_refs"])
        return {"status": "release_not_executed", "contrast_sha256": digest,
                "provenance_sha256": provenance_digest, "state_digest": state_digest,
                "message": "Whole-task release has not executed. Your exact contrast must appear in a later model request before the same contrast can authorize release. You may investigate, intervene, or revise it."}

    def render_root(self, handoff, workspace=None):
        reset = self.root_reorientation
        if reset is not None:
            if not handoff or _handoff_identity(handoff) != reset["handoff"]:
                self._clear_root("stale_handoff")
                return None
            if workspace is None:
                raise ValueError("Root Horizon Reset requires the current Task Book identity")
            self._refresh_root_reorientation(workspace)
            surface = _rhr_surface(reset)
            self.audit("rhr_surface_prepared", root_horizon_digest=reset["root_horizon_digest"],
                       surface_sha256=hashlib.sha256(surface.encode("utf-8")).hexdigest(),
                       handoff=reset["handoff"])
            return surface
        active = self.root_contrast
        if active is None:
            return None
        identity = {key: handoff.get(key) for key in ("request_id", "generation", "cursor")} if handoff else None
        if identity != active["handoff"]:
            self._clear_root("stale_handoff")
            return None
        surface = _surface(active)
        self.audit("crs_surface_prepared", contrast_sha256=active["sha256"],
                   provenance_sha256=active["provenance_sha256"],
                   state_digest=active["state_digest"], handoff=identity,
                   surface_sha256=hashlib.sha256(surface.encode("utf-8")).hexdigest())
        return surface

    def surface_visible(self, request_id):
        reset = self.root_reorientation
        if reset is not None:
            reset["surfaced"] = True
            reset["surfaced_request_id"] = request_id
            self.audit("rhr_surface_injected", root_horizon_digest=reset["root_horizon_digest"],
                       request_id=request_id, handoff=reset["handoff"])
            return
        active = self.root_contrast
        if active is not None:
            active["surfaced"] = True
            active["surfaced_request_id"] = request_id
            self.audit("crs_surface_injected", contrast_sha256=active["sha256"],
                       provenance_sha256=active["provenance_sha256"],
                       state_digest=active["state_digest"],
                       handoff=active["handoff"], request_id=request_id)

    def _clear_root(self, reason):
        reset = self.root_reorientation
        if reset is not None:
            self.audit("rhr_abandoned", root_horizon_digest=reset["root_horizon_digest"],
                       reason=reason, handoff=reset["handoff"])
            self.root_reorientation = None
        active = self.root_contrast
        if active is not None:
            self.audit("crs_abandoned", contrast_sha256=active["sha256"],
                       state_digest=active["state_digest"],
                       handoff=active["handoff"], reason=reason)
            self.root_contrast = None

    def abandon(self, disposition):
        self._clear_root(disposition)
        super().abandon(disposition)

    def end_review(self, reason):
        self._clear_root(reason)
        super().end_review(reason)
