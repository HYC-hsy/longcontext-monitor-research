"""Review-local contrastive root release; mechanical provenance, no verdicts."""

from __future__ import annotations

import hashlib
import json
import re

from .ase_v0 import ReconsiderationBoundary


_PUBLIC = re.compile(r"task/public_events\.jsonl#([1-9][0-9]*)\Z")
_DIALOGUE = re.compile(r"monitor/audit/dialogue\.jsonl#([1-9][0-9]*)\Z")
_FIELDS = {"alternative", "grounding", "ground_refs", "discrimination", "observation_refs"}
_MAX_TEXT = {"alternative": 1200, "grounding": 1200, "discrimination": 1600}
CRS_PUBLIC_RESULT_EXCERPT_CHARS = 640
CRS_SURFACE_MAX_CHARS = 16000


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
    if not observation and ref in {"task/original_task.txt", "monitor/reference.md"}:
        path = workspace.resolve_read(ref)
        return {"locator": ref, "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    public = _PUBLIC.fullmatch(ref)
    if public:
        cursor = int(public.group(1))
        event = _row(workspace.resolve_read("task/public_events.jsonl"), cursor)
        if not isinstance(event, dict) or event.get("archive_sequence") != cursor:
            raise ValueError("Public locator must match an archived event cursor")
        if observation:
            results = event.get("tool_results")
            if not isinstance(results, list) or not results:
                raise ValueError("Public observation requires an actual tool result")
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


def validate_contrast(value, workspace):
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("contrast requires exactly alternative, grounding, ground_refs, discrimination, observation_refs")
    for field, maximum in _MAX_TEXT.items():
        text = value[field]
        if not isinstance(text, str) or not text.strip() or len(text) > maximum:
            raise ValueError(f"contrast.{field} must be non-empty and at most {maximum} characters")
    provenance = {}
    for field, observation in (("ground_refs", False), ("observation_refs", True)):
        refs = value[field]
        if not isinstance(refs, list) or not 1 <= len(refs) <= 4 or len(set(map(str, refs))) != len(refs):
            raise ValueError(f"contrast.{field} requires 1–4 distinct locators")
        provenance[field] = [_reference(ref, workspace, observation) for ref in refs]
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
        "Model-authored contrast:\n" + active["canonical"] + "\n"
        "Resolved mechanical provenance for cited sources:\n" +
        _canonical(_display(active["provenance"]))
    )
    if len(surface) > CRS_SURFACE_MAX_CHARS:
        raise ValueError(f"CRS surface exceeds {CRS_SURFACE_MAX_CHARS} characters; shorten contrast or references")
    return surface


class ContrastiveReleaseBoundary(ReconsiderationBoundary):
    """Extends ASE reconsideration only for root allow_complete."""

    def __init__(self, audit, visible_context):
        super().__init__(audit, visible_context)
        self.root_contrast = None

    def begin_review(self, review_id):
        super().begin_review(review_id)
        self.root_contrast = None

    def root_release(self, contrast, handoff, workspace):
        canonical, digest, provenance = validate_contrast(contrast, workspace)
        provenance_text = _canonical(provenance)
        provenance_digest = hashlib.sha256(provenance_text.encode("utf-8")).hexdigest()
        state_digest = hashlib.sha256((canonical + "\n" + provenance_text).encode("utf-8")).hexdigest()
        identity = {key: handoff.get(key) for key in ("request_id", "generation", "cursor")}
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
        self.audit("crs_release_attempted", contrast_sha256=digest,
                   provenance_sha256=provenance_digest, state_digest=state_digest, handoff=identity,
                   ground_refs=provenance["ground_refs"],
                   observation_refs=provenance["observation_refs"], model_turn=self.model_turn)
        if (prior is not None and prior["canonical"] == canonical
                and prior["state_digest"] == state_digest and prior["surfaced"]
                and self.model_turn is not None and self.model_turn > prior["proposed_turn"]):
            self.audit("crs_confirmed", contrast_sha256=digest,
                       provenance_sha256=provenance_digest, state_digest=state_digest, handoff=identity,
                       surfaced_request_id=prior["surfaced_request_id"], model_turn=self.model_turn)
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

    def render_root(self, handoff):
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
        active = self.root_contrast
        if active is not None:
            active["surfaced"] = True
            active["surfaced_request_id"] = request_id
            self.audit("crs_surface_injected", contrast_sha256=active["sha256"],
                       provenance_sha256=active["provenance_sha256"],
                       state_digest=active["state_digest"],
                       handoff=active["handoff"], request_id=request_id)

    def _clear_root(self, reason):
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
