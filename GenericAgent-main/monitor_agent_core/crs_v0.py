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
            return {"locator": ref, "source": "task_tool_result",
                    "task_turn": event.get("task_turn"),
                    "archive_sequence": event.get("archive_sequence"),
                    "tool_result_count": len(results),
                    "tool_result_sha256": hashlib.sha256(json.dumps(
                        results, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()}
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
        fields = ("path", "start", "lines", "offset", "sha256", "truncated",
                  "status", "session_id", "exit_code", "error_type", "cancelled",
                  "running", "output_path")
        return {"locator": ref, "source": "supervisor_tool_result",
                "tool_name": call["name"], "tool_id": receipt["tool_id"],
                "receipt_sha256": hashlib.sha256(json.dumps(
                    data, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
                "lifecycle": {key: data[key] for key in fields if key in data}}
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
        identity = {key: handoff.get(key) for key in ("request_id", "generation", "cursor")}
        prior = self.root_contrast
        if prior is not None and prior["handoff"] != identity:
            self._clear_root("stale_handoff")
            prior = None
        self.audit("crs_release_attempted", contrast_sha256=digest, handoff=identity,
                   ground_refs=provenance["ground_refs"],
                   observation_refs=provenance["observation_refs"], model_turn=self.model_turn)
        if (prior is not None and prior["canonical"] == canonical and prior["surfaced"]
                and self.model_turn is not None and self.model_turn > prior["proposed_turn"]):
            self.audit("crs_confirmed", contrast_sha256=digest, handoff=identity,
                       surfaced_request_id=prior["surfaced_request_id"], model_turn=self.model_turn)
            self.root_contrast = None
            return None
        if prior is not None and prior["canonical"] != canonical:
            self._clear_root("revised")
            self.audit("crs_revised", old_sha256=prior["sha256"], new_sha256=digest,
                       handoff=identity)
        if prior is None or prior["canonical"] != canonical:
            self.root_contrast = {"canonical": canonical, "sha256": digest,
                                  "handoff": identity, "proposed_turn": self.model_turn,
                                  "surfaced": False, "surfaced_request_id": None,
                                  "provenance": provenance}
            self.audit("crs_proposed", contrast_sha256=digest, handoff=identity,
                       canonical_contrast=canonical, model_turn=self.model_turn,
                       ground_refs=provenance["ground_refs"],
                       observation_refs=provenance["observation_refs"])
        return {"status": "release_not_executed", "contrast_sha256": digest,
                "message": "Whole-task release has not executed. Your exact contrast must appear in a later model request before the same contrast can authorize release. You may investigate, intervene, or revise it."}

    def render_root(self, handoff):
        active = self.root_contrast
        if active is None:
            return None
        identity = {key: handoff.get(key) for key in ("request_id", "generation", "cursor")} if handoff else None
        if identity != active["handoff"]:
            self._clear_root("stale_handoff")
            return None
        surface = ("Contrastive Release State — your own proposed whole-task release cognition, "
                   "not task truth or runtime verification. Release has not executed. "
                   "You may investigate, intervene, or revise this contrast. To release on it, "
                   "submit this same exact contrast again after seeing it in this model request.\n"
                   + active["canonical"])
        self.audit("crs_surface_prepared", contrast_sha256=active["sha256"],
                   handoff=identity, surface_sha256=hashlib.sha256(surface.encode("utf-8")).hexdigest())
        return surface

    def surface_visible(self, request_id):
        active = self.root_contrast
        if active is not None:
            active["surfaced"] = True
            active["surfaced_request_id"] = request_id
            self.audit("crs_surface_injected", contrast_sha256=active["sha256"],
                       handoff=active["handoff"], request_id=request_id)

    def _clear_root(self, reason):
        active = self.root_contrast
        if active is not None:
            self.audit("crs_abandoned", contrast_sha256=active["sha256"],
                       handoff=active["handoff"], reason=reason)
            self.root_contrast = None

    def abandon(self, disposition):
        self._clear_root(disposition)
        super().abandon(disposition)

    def end_review(self, reason):
        self._clear_root(reason)
        super().end_review(reason)
