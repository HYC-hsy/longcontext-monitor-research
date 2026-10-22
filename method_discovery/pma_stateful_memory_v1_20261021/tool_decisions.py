"""Offline native-tool reference compilers; not connected to a provider or engine.

These compilers validate tool structure and restore host-owned fields. They do
not replace validate_audit_result (with the caller's catalog/archive) or
validate_selection (with the caller's snapshot and visible references).
"""

from copy import deepcopy

from .audit import ISSUE_KINDS
from .source import ContractError, canonical, fields, integer, nonempty
from .tool_native import NativeToolError, validate_tool_arguments


def _object(properties, optional=()):
    return {"type": "object", "properties": properties,
            "required": sorted(set(properties) - set(optional)),
            "additionalProperties": False}


def _array(items, **limits):
    return {"type": "array", "items": items, **limits}


def _enum(*values):
    return {"type": "string", "enum": list(values)}


_TEXT = {"type": "string", "minLength": 1}
_INT = {"type": "integer", "minimum": 1}
_NULL = {"type": "null"}
_SOURCE = _object({"evidence_id": _TEXT, "quote": _TEXT})
_GAP = _object({"type": _enum("gap"), "gap_id": _TEXT,
                "revision": _INT, "task_version": _INT})
_GOAL_DELTA = _object({"type": _enum("goal_delta"), "goal_delta_id": _TEXT,
                       "from_task_version": _INT, "to_task_version": _INT})
_BOUND = _object({"snapshot": _enum("base", "candidate", "archive"),
    "target": _object({"kind": _TEXT, "id": _TEXT, "revision": _INT},
                      optional=("revision",)), "field_path": _TEXT})
_WITNESS = {"anyOf": [
    _object({"kind": _enum("source"), "ref": _SOURCE}),
    _object({"kind": _enum("field"), "field": _BOUND, "exact_value": {}})]}
_ISSUE = _object({"issue_id": _TEXT, "kind": _enum(*sorted(ISSUE_KINDS)),
    "target": _BOUND, "related_targets": _array(_BOUND),
    "explanation": _TEXT, "witnesses": _array(_WITNESS, minItems=1),
    "repair_constraint": _TEXT})
_ASSESSMENT = _object({"resolution_id": _TEXT,
    "verdict": _enum("supported", "unsupported", "uncertain"),
    "assessed_scope": {"type": "object"}, "explanation": _TEXT,
    "basis_refs": _array({"anyOf": [_SOURCE, _GOAL_DELTA, _GAP]}),
    "blocking_issue_ids": _array(_TEXT)})
_AUDIT = _object({"outcome": _enum("clean", "issues", "unusable"),
    "issues": _array(_ISSUE), "closure_assessments": _array(_ASSESSMENT),
    "unusable_reason": {"anyOf": [_NULL, _object({
        "code": _enum("insufficient_context", "ambiguous_input",
                      "cannot_complete_audit"), "detail": {"type": "string"}})]}})
_SELECTION_REF = {"anyOf": [
    _object({"type": _enum("state"), "record_id": _TEXT, "revision": _INT}),
    _object({"type": _enum("requirement"), "requirement_id": _TEXT,
             "revision": _INT, "task_version": _INT}), _GAP]}
_SELECTION = _object({"decision": _enum("silent", "remind"),
    "refs": {"anyOf": [_NULL, _array(_SELECTION_REF, minItems=1, maxItems=3)]},
    "context_for_action": {"anyOf": [_NULL, {**_TEXT, "maxLength": 1200}]}})


def _definition(name, description, parameters):
    # No provider-specific strict-mode compatibility is asserted here.
    return [{"type": "function", "function": {"name": name,
        "description": description, "parameters": deepcopy(parameters)}}]


def audit_tool_definitions():
    """One audit call, with exact typed issue refs and compact closure IDs."""
    return _definition("submit_audit", "Submit one audit of the bound view. "
        "For unusable, supply no conclusions. Closure IDs come from the view; "
        "the host restores gap identities, closure kinds and binding.", _AUDIT)


def selection_tool_definitions():
    """One explicit decision; silent requires null refs and context."""
    return _definition("submit_selection", "Submit one selection. Use null refs "
        "and context_for_action for silent; remind requires 1–3 exact visible "
        "typed references and a nonempty note of at most 1200 characters.", _SELECTION)


def _arguments(calls, name, schema):
    if type(calls) is not list or len(calls) != 1:
        raise ContractError("tool_call_count")
    # Validate the whole call, including outer keys, before using fields().
    # This boundary consumes normalized native dict arguments, not JSON text.
    if (type(calls[0]) is not dict or
            type(calls[0].get("arguments")) is not dict):
        raise ContractError("tool_argument_schema", "arguments_not_object")
    call_schema = _object({"name": _enum(name), "arguments": schema})
    try:
        call = validate_tool_arguments(calls[0], call_schema)
    except NativeToolError as error:
        raise ContractError("tool_argument_schema", error.code) from error
    return call["arguments"]


def compile_audit(calls, *, view):
    """Expand only frozen-view identities; caller must run domain validation."""
    args = _arguments(calls, "submit_audit", _AUDIT)
    if args["outcome"] == "unusable":
        if args["unusable_reason"] is None or args["issues"] or args["closure_assessments"]:
            raise ContractError("unusable_with_conclusions_or_missing_reason")
    else:
        if args["unusable_reason"] is not None:
            raise ContractError("contradictory_unusable_reason")
        if (args["outcome"] == "clean" and args["issues"] or
                args["outcome"] == "issues" and not args["issues"]):
            raise ContractError("contradictory_audit_outcome")
        manifest = {}
        for entry in view["resolve_manifest"]:
            resolution_id = nonempty(entry["resolution_id"], "resolution_id")
            if resolution_id in manifest:
                raise ContractError("duplicate_manifest_resolution")
            manifest[resolution_id] = entry
        seen = set()
        for assessment in args["closure_assessments"]:
            resolution_id = assessment["resolution_id"]
            if resolution_id not in manifest:
                raise ContractError("unknown_resolution_id")
            if resolution_id in seen:
                raise ContractError("duplicate_closure_assessment")
            seen.add(resolution_id)
            entry = manifest[resolution_id]
            for key in ("gap_before", "gap_after"):
                gap = entry[key]
                assessment[key] = None if gap is None else {
                    "type": "gap", "gap_id": gap["gap_id"],
                    "revision": gap["revision"], "task_version": gap["task_version"]}
            assessment["closure_kind"] = entry["closure_kind"]
        if seen != set(manifest):
            raise ContractError("closure_assessment_mismatch")
    return deepcopy({"protocol": "audit-result/2", "binding": view["binding"], **args})


def compile_selection(calls, *, binding):
    """Restore the host binding, never accept model-echoed version fields."""
    args = _arguments(calls, "submit_selection", _SELECTION)
    fields(binding, {"state_version", "task_version", "phase2_view_id"})
    integer(binding["state_version"], "state_version")
    integer(binding["task_version"], "task_version", 1)
    nonempty(binding["phase2_view_id"], "phase2_view_id")
    result = {"decision": args["decision"], **deepcopy(binding)}
    if args["decision"] == "silent":
        if args["refs"] is not None or args["context_for_action"] is not None:
            raise ContractError("silent_with_content")
    else:
        if args["refs"] is None or args["context_for_action"] is None:
            raise ContractError("remind_missing_content")
        identities = [canonical(ref) for ref in args["refs"]]
        if len(set(identities)) != len(identities):
            raise ContractError("selection_duplicate_ref")
        result.update(refs=args["refs"], context_for_action=args["context_for_action"])
    return result
