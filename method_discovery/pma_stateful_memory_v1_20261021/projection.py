"""Deterministic audit/maintenance view of the frozen current workset."""

from __future__ import annotations

from copy import deepcopy

from .source import ContractError


def visible_existing(base: dict, work: dict) -> set[tuple[str, str]]:
    result = {("requirement", item["requirement_id"]) for item in
              base["B"]["G"]["specifications"]}
    result.update(("gap", item["gap_id"]) for item in work["mandatory"]["open_gaps"])
    for bundle in [*work["mandatory"]["bundles"], *work["optional_bundles"]]:
        result.add(("state", bundle["state"]["record_id"]))
        current_revisions = {item["record_id"]: item["revision"] for item in
                             base["B"]["W"]["states"]}
        result.update(("state", item["record_id"]) for item in
            bundle.get("linked_state_versions", []) if current_revisions.get(
                item["record_id"]) == item["revision"])
        result.update(("entity", item["entity_id"]) for item in bundle["entities"])
        result.update(("relation", item["relation_id"]) for item in
                      bundle["relations"])
        result.update(("gap", item["gap_id"]) for item in
                      bundle["linked_closed_gaps"])
    return result


def project_snapshot(full: dict, base: dict, work: dict) -> dict:
    """Keep same scalar root and original array order; never mutate full state."""
    permitted = visible_existing(base, work)
    old = base["B"]
    new = full["B"]
    keys = (("entity", "W", "entities", "entity_id"),
            ("state", "W", "states", "record_id"),
            ("relation", "W", "relations", "relation_id"),
            ("requirement", "G", "specifications", "requirement_id"),
            ("gap", "B", "DeltaE", "gap_id"),
            ("gap", "B", "DeltaA", "gap_id"))
    view = deepcopy(full)
    for kind, parent, name, id_field in keys:
        old_items = old[name] if parent == "B" else old[parent][name]
        new_items = new[name] if parent == "B" else new[parent][name]
        old_ids = {item[id_field] for item in old_items}
        selected = [item for item in new_items if (kind, item[id_field]) in
                    permitted or item[id_field] not in old_ids]
        if parent == "B":
            view["B"][name] = deepcopy(selected)
        else:
            view["B"][parent][name] = deepcopy(selected)
    if len(view["B"]["W"]["states"]) != len({item["record_id"] for item in
            view["B"]["W"]["states"]}):
        raise ContractError("duplicate_projected_state")
    return view
