"""Reversible audit view and all-or-nothing audit-result validation."""

from __future__ import annotations

from copy import deepcopy

from .source import ContractError, SourceCatalog, canonical, digest, fields, nonempty


LISTS = (("G", "specifications", "requirement_id", "requirement"),
         ("W", "entities", "entity_id", "entity"),
         ("W", "states", "record_id", "state"),
         ("W", "relations", "relation_id", "relation"),
         (None, "DeltaE", "gap_id", "gap"),
         (None, "DeltaA", "gap_id", "gap"))
ISSUE_KINDS = {"unsupported_claim", "observation_conflict", "scope_overreach",
               "temporal_misclassification", "source_role_misuse",
               "goal_misinterpretation", "internal_inconsistency",
               "unjustified_gap_closure", "unjustified_information_loss"}


def _list(belief: dict, parent: str | None, name: str) -> list:
    return belief[parent][name] if parent == "G" else (
        belief["W"][name] if parent == "W" else belief[name])


def _replace_list(belief: dict, parent: str | None, name: str,
                  replacement: list) -> None:
    if parent == "G":
        belief["G"][name] = replacement
    elif parent == "W":
        belief["W"][name] = replacement
    else:
        belief[name] = replacement


def _ref(kind: str, body: dict, name: str) -> dict:
    result = {"kind": kind, "id": body[name]}
    if "revision" in body:
        result["revision"] = body["revision"]
    return result


def _diff(before: object, after: object, prefix: str = "") -> list[str]:
    if canonical(before) == canonical(after):
        return []
    if type(before) is dict and type(after) is dict:
        result = []
        for key in sorted(set(before) | set(after)):
            result.extend(_diff(before.get(key), after.get(key),
                                prefix + "." + key if prefix else key))
        return result
    return [prefix or "$root"]


def _replace_refs(layout: dict, bodies: dict[str, dict]) -> dict:
    restored = deepcopy(layout)
    for parent, name, _id_field, _kind in LISTS:
        value = []
        for marker in _list(restored["B"], parent, name):
            marker = fields(marker, {"$ref"})
            if marker["$ref"] not in bodies:
                raise ContractError("audit_layout_missing_object", marker["$ref"])
            value.append(deepcopy(bodies[marker["$ref"]]))
        _replace_list(restored["B"], parent, name, value)
    return restored


class AuditCodec:
    """No semantic truncation: either reconstruct both exact snapshots or fail."""

    def encode(self, before: dict, candidate: dict, *, binding: dict,
               sources: list[dict], observations: dict,
               operation_index: list[dict], resolve_manifest: list[dict],
               contextual_objects: list[dict] | None = None,
               goal_ledger: dict | None = None) -> dict:
        before_layout = deepcopy(before)
        candidate_layout = deepcopy(candidate)
        shared = []
        changed = []
        added = []
        before_bodies = {}
        candidate_bodies = {}
        required_coverage = []
        for parent, name, key, kind in LISTS:
            old = {item[key]: item for item in _list(before["B"], parent, name)}
            new = {item[key]: item for item in _list(candidate["B"], parent, name)}
            if set(old) - set(new):
                raise ContractError("implicit_object_deletion", name)
            old_markers = []
            new_markers = []
            for item in _list(before["B"], parent, name):
                marker = f"before:{parent or 'B'}.{name}:{item[key]}"
                before_bodies[marker] = item
                old_markers.append({"$ref": marker})
            for item in _list(candidate["B"], parent, name):
                marker = f"candidate:{parent or 'B'}.{name}:{item[key]}"
                candidate_bodies[marker] = item
                new_markers.append({"$ref": marker})
                required_coverage.append(_ref(kind, item, key))
                if item[key] not in old:
                    added.append({"after_ref": marker, "body": item})
                elif canonical(old[item[key]]) == canonical(item):
                    shared.append({"object_ref": marker, "body": item})
                else:
                    changed.append({"before_ref": f"before:{parent or 'B'}.{name}:{item[key]}",
                                    "before_body": old[item[key]],
                                    "after_ref": marker, "after_body": item})
            _replace_list(before_layout["B"], parent, name, old_markers)
            _replace_list(candidate_layout["B"], parent, name, new_markers)
        if candidate["B"]["F"] is not None:
            required_coverage.append({"kind": "focus", "id": "F"})
        for entry in changed:
            entry["changed_field_paths"] = _diff(entry["before_body"],
                                                 entry["after_body"])
        view = {"binding": binding, "shared_objects": shared,
                "changed_objects": changed, "added_objects": added,
                "operation_index": operation_index,
                "before_layout": before_layout,
                "candidate_layout": candidate_layout,
                "contextual_objects": contextual_objects or [],
                "source_catalog": sources, "observations": observations,
                "goal_ledger": goal_ledger,
                "budget_notice": {"input_proxy_tokens_limit": 32768,
                                  "output_provider_tokens_limit": 8192},
                "required_coverage": required_coverage,
                "resolve_manifest": resolve_manifest, "view_omissions": []}
        self.verify(view, before, candidate)
        view["binding"] = {**binding, "audit_view_hash": digest(view)}
        return view

    def verify(self, view: dict, before: dict, candidate: dict) -> None:
        old_bodies = {}
        new_bodies = {}
        for entry in view["shared_objects"]:
            new_bodies[entry["object_ref"]] = entry["body"]
            old_bodies[entry["object_ref"].replace("candidate:", "before:")] = entry["body"]
        for entry in view["changed_objects"]:
            old_bodies[entry["before_ref"]] = entry["before_body"]
            new_bodies[entry["after_ref"]] = entry["after_body"]
        for entry in view["added_objects"]:
            new_bodies[entry["after_ref"]] = entry["body"]
        if digest(_replace_refs(view["before_layout"], old_bodies)) != digest(before):
            raise ContractError("audit_before_reconstruction_mismatch")
        if digest(_replace_refs(view["candidate_layout"], new_bodies)) != digest(candidate):
            raise ContractError("audit_candidate_reconstruction_mismatch")


def _targets(view: dict) -> dict[str, dict[tuple[str, str], dict]]:
    result = {"base": {}, "candidate": {}, "archive": {}}
    kinds = {"G.specifications": "requirement", "W.entities": "entity",
             "W.states": "state", "W.relations": "relation",
             "B.DeltaE": "gap", "B.DeltaA": "gap"}
    def put(snapshot: str, marker: str, body: dict) -> None:
        _, path, identifier = marker.split(":", 2)
        result[snapshot][(kinds[path], identifier)] = body
    for entry in view["shared_objects"]:
        put("candidate", entry["object_ref"], entry["body"])
        put("base", entry["object_ref"].replace("candidate:", "before:"),
            entry["body"])
    for entry in view["changed_objects"]:
        put("base", entry["before_ref"], entry["before_body"])
        put("candidate", entry["after_ref"], entry["after_body"])
    for entry in view["added_objects"]:
        put("candidate", entry["after_ref"], entry["body"])
    for snapshot, layout in (("base", view["before_layout"]),
                             ("candidate", view["candidate_layout"])):
        if layout["B"]["F"] is not None:
            result[snapshot][("focus", "F")] = layout["B"]["F"]
    return result


def _field_value(body: dict, path: str) -> object:
    current = body
    for part in nonempty(path, "field_path").split("."):
        if type(current) is dict and part in current:
            current = current[part]
        elif type(current) is list and part.isdecimal() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ContractError("invalid_field_path", path)
    return current


def _bound_field(value: object, targets: dict) -> dict:
    value = fields(value, {"snapshot", "target", "field_path"})
    if value["snapshot"] not in {"base", "candidate", "archive"}:
        raise ContractError("invalid_bound_snapshot")
    target = fields(value["target"], {"kind", "id"}, {"revision"})
    identity = (target["kind"], target["id"])
    key = (*identity, target.get("revision")) if value["snapshot"] == "archive" else identity
    body = targets[value["snapshot"]].get(key)
    if body is None:
        raise ContractError("unknown_target_id", target["id"])
    if "revision" in body and body["revision"] != target.get("revision"):
        raise ContractError("version_mismatch", target["id"])
    _field_value(body, value["field_path"])
    return value


def validate_audit_result(raw: object, *, view: dict,
                          catalog: SourceCatalog, archive: dict | None = None) -> dict:
    """One malformed issue invalidates the whole result; never filter to clean."""
    result = fields(raw, {"protocol", "binding", "coverage", "outcome", "issues",
                          "closure_assessments", "unusable_reason"})
    if result["protocol"] != "audit-result/1" or result["binding"] != view["binding"]:
        raise ContractError("binding_mismatch")
    if result["outcome"] not in {"clean", "issues", "unusable"}:
        raise ContractError("invalid_audit_outcome")
    for key in ("coverage", "issues", "closure_assessments"):
        if type(result[key]) is not list:
            raise ContractError("invalid_array", key)
    expected = {canonical(item) for item in view["required_coverage"]}
    actual = [canonical(item) for item in result["coverage"]]
    if set(actual) != expected or len(actual) != len(expected):
        raise ContractError("coverage_mismatch")
    if result["outcome"] == "unusable":
        reason = fields(result["unusable_reason"], {"code", "detail"})
        if reason["code"] not in {"insufficient_context", "ambiguous_input",
                                   "cannot_complete_audit"}:
            raise ContractError("invalid_unusable_reason")
        if result["issues"] or result["closure_assessments"]:
            raise ContractError("unusable_with_conclusions")
        return result
    if result["unusable_reason"] is not None:
        raise ContractError("contradictory_unusable_reason")
    if (result["outcome"] == "clean" and result["issues"] or
            result["outcome"] == "issues" and not result["issues"]):
        raise ContractError("contradictory_audit_outcome")
    targets = _targets(view)
    targets["archive"] = archive or {}
    issue_ids = set()
    for issue in result["issues"]:
        issue = fields(issue, {"issue_id", "kind", "target", "related_targets",
                               "explanation", "witnesses", "repair_constraint"})
        issue_id = nonempty(issue["issue_id"], "issue_id")
        if issue_id in issue_ids or issue["kind"] not in ISSUE_KINDS:
            raise ContractError("invalid_issue_kind_or_id")
        issue_ids.add(issue_id)
        main = _bound_field(issue["target"], targets)
        if main["snapshot"] != "candidate":
            raise ContractError("issue_target_not_candidate")
        if type(issue["related_targets"]) is not list or type(issue["witnesses"]) is not list:
            raise ContractError("invalid_issue_array")
        if not issue["witnesses"]:
            raise ContractError("missing_issue_witness")
        for related in issue["related_targets"]:
            _bound_field(related, targets)
        nonempty(issue["explanation"], "explanation")
        nonempty(issue["repair_constraint"], "repair_constraint")
        for witness in issue["witnesses"]:
            if type(witness) is not dict:
                raise ContractError("invalid_witness")
            if witness.get("kind") == "source":
                fields(witness, {"kind", "ref"})
                catalog.resolve(witness["ref"], purpose="audit")
            elif witness.get("kind") == "field":
                fields(witness, {"kind", "field", "exact_value"})
                bound = _bound_field(witness["field"], targets)
                identity = (bound["target"]["kind"], bound["target"]["id"])
                key = (*identity, bound["target"].get("revision")) if bound[
                    "snapshot"] == "archive" else identity
                body = targets[bound["snapshot"]][key]
                if canonical(_field_value(body, bound["field_path"])) != canonical(
                        witness["exact_value"]):
                    raise ContractError("field_witness_mismatch")
            else:
                raise ContractError("invalid_witness_kind")
    manifest = view["resolve_manifest"]
    if len(result["closure_assessments"]) != len(manifest):
        raise ContractError("closure_assessment_mismatch")
    expected_ids = {item["resolution_id"] for item in manifest}
    actual_ids = [item.get("resolution_id") for item in result["closure_assessments"]]
    if set(actual_ids) != expected_ids or len(actual_ids) != len(expected_ids):
        raise ContractError("closure_assessment_mismatch")
    for item in result["closure_assessments"]:
        item = fields(item, {"resolution_id", "gap_before", "gap_after",
                             "closure_kind", "verdict", "assessed_scope",
                             "explanation", "basis_refs", "blocking_issue_ids"})
        expected = next(entry for entry in manifest if entry["resolution_id"] ==
                        item["resolution_id"])
        def gap_identity(body):
            if body is None:
                return None
            return {"type": "gap", "gap_id": body["gap_id"],
                    "revision": body["revision"],
                    "task_version": body["task_version"]}
        if (item["gap_before"] != gap_identity(expected["gap_before"]) or
                item["gap_after"] != gap_identity(expected["gap_after"]) or
                item["closure_kind"] != expected["closure_kind"]):
            raise ContractError("closure_assessment_mismatch")
        if type(item["blocking_issue_ids"]) is not list or type(
                item["basis_refs"]) is not list or type(item["assessed_scope"]) is not dict:
            raise ContractError("invalid_closure_assessment")
        nonempty(item["explanation"], "closure.explanation")
        if item["verdict"] not in {"supported", "unsupported", "uncertain"}:
            raise ContractError("invalid_closure_verdict")
        if any(issue_id not in issue_ids for issue_id in item["blocking_issue_ids"]):
            raise ContractError("unknown_blocking_issue")
        if item["verdict"] == "supported" and item["blocking_issue_ids"]:
            raise ContractError("contradictory_assessment")
        if result["outcome"] == "clean" and item["verdict"] != "supported":
            raise ContractError("contradictory_assessment")
        if item["verdict"] != "supported" and not (
                set(item["blocking_issue_ids"]) & issue_ids):
            raise ContractError("missing_blocking_issue")
        for ref in item["basis_refs"]:
            if type(ref) is not dict:
                raise ContractError("invalid_basis_ref")
            if "evidence_id" in ref:
                catalog.resolve(ref, purpose="audit", allowed_kinds=(
                    {"tool_result", "user_report"} if item["closure_kind"] ==
                    "environment_supported" else None))
            elif ref.get("type") == "goal_delta":
                if ref not in view["candidate_layout"]["B"]["G"]["goal_deltas"]:
                    raise ContractError("unknown_goal_delta")
            elif ref.get("type") == "gap":
                replacement = (expected["gap_after"].get("closure") or {}).get(
                    "replacement_gap_ref")
                if ref != replacement or ("gap", ref.get("gap_id")) not in targets[
                        "candidate"]:
                    raise ContractError("unknown_gap_ref")
            else:
                raise ContractError("invalid_basis_ref")
        expected_kind = {"environment_supported": "evidence_id",
                         "goal_changed": "goal_delta",
                         "merged_into": "gap"}.get(item["closure_kind"])
        if expected_kind is None or not any((expected_kind == "evidence_id" and
                "evidence_id" in ref) or ref.get("type") == expected_kind for ref in
                item["basis_refs"]):
            raise ContractError("closure_basis_mismatch")
    return result
