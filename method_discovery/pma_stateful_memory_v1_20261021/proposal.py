"""Strict maintenance proposal and one-time application to an isolated base."""

from __future__ import annotations

from copy import deepcopy

from .schema import validate_snapshot, enum, refs
from .source import ContractError, SourceCatalog, digest, fields, integer, nonempty


PROPOSAL_FIELDS = {"protocol", "request_id", "active_task_version",
                   "base_state_version", "world_patch", "specification_upserts",
                   "gap_upserts", "gap_resolutions", "gap_reopens", "focus"}
PATCH_FIELDS = {"entity_upserts", "state_upserts", "relation_upserts",
                "record_transitions"}


def validate_proposal(raw: object, *, request_id: str,
                      task_version: int, base_version: int) -> dict:
    proposal = fields(raw, PROPOSAL_FIELDS)
    if proposal["protocol"] != "maintenance-proposal/1" or proposal[
            "request_id"] != request_id:
        raise ContractError("binding_mismatch")
    if (proposal["active_task_version"] != task_version or
            proposal["base_state_version"] != base_version):
        raise ContractError("version_mismatch")
    def reject_stored_wire(value):
        if type(value) is dict:
            if set(value) == {"source_id", "start", "end", "quote"}:
                raise ContractError("stored_ref_in_wire_proposal")
            for member in value.values():
                reject_stored_wire(member)
        elif type(value) is list:
            for member in value:
                reject_stored_wire(member)
    reject_stored_wire(proposal)
    patch = fields(proposal["world_patch"], PATCH_FIELDS)
    for key in PATCH_FIELDS:
        if type(patch[key]) is not list:
            raise ContractError("invalid_array", key)
    for key in ("specification_upserts", "gap_upserts", "gap_resolutions",
                "gap_reopens"):
        if type(proposal[key]) is not list:
            raise ContractError("invalid_array", key)
    seen: set[tuple[str, str]] = set()
    groups = [("entity", patch["entity_upserts"], "entity_id"),
              ("state", patch["state_upserts"], "record_id"),
              ("relation", patch["relation_upserts"], "relation_id"),
              ("state", patch["record_transitions"], "record_ref"),
              ("requirement", proposal["specification_upserts"], "requirement_id")]
    groups.extend(("gap", proposal[key], "gap_id") for key in
                  ("gap_upserts", "gap_resolutions", "gap_reopens"))
    for kind, items, key in groups:
        for item in items:
            if type(item) is not dict:
                raise ContractError("wrong_object_type", kind)
            identifier = item.get(key)
            if key == "record_ref" and type(identifier) is dict:
                identifier = identifier.get("record_id")
            identifier = nonempty(identifier, key)
            identity = (kind, identifier)
            if identity in seen:
                raise ContractError("conflicting_operations", identifier)
            seen.add(identity)
    item_contracts = (
        (patch["entity_upserts"], {"entity_id", "entity_type", "display_name"}),
        (patch["relation_upserts"], {"relation_id", "from_entity_id",
                                     "to_entity_id", "predicate", "anchored_by"}),
        (patch["record_transitions"], {"record_ref", "to_status", "reason",
                                       "evidence_refs"}),
        (proposal["specification_upserts"], {"requirement_id", "revision",
            "task_version", "interpretation", "source_refs", "status", "retirement"}))
    for items, required in item_contracts:
        for item in items:
            fields(item, required)
    for item in patch["relation_upserts"]:
        fields(item["anchored_by"], {"type", "record_id", "revision"})
    for item in patch["record_transitions"]:
        fields(item["record_ref"], {"type", "record_id", "revision"})
        if item["record_ref"]["type"] != "state":
            raise ContractError("invalid_state_ref")
        enum(item["to_status"], {"historical_only", "contested", "retracted"},
             "transition_status")
        nonempty(item["reason"], "transition.reason")
        if type(item["evidence_refs"]) is not list:
            raise ContractError("invalid_array", "transition.evidence_refs")
    for item in patch["state_upserts"]:
        if type(item) is not dict:
            raise ContractError("wrong_object_type", "state")
        common = {"record_id", "revision", "entity_id", "scope", "use_status",
                  "updated_at_step", "supersedes", "kind"}
        fields(item, common | ({"claim"} if item.get("kind") == "knowledge" else
                               {"episode", "lesson"}))
    gap_fields = {"gap_id", "revision", "task_version", "gap_kind", "target",
                  "reason", "goal_refs", "record_refs", "status", "closure"}
    for key in ("gap_upserts", "gap_resolutions", "gap_reopens"):
        for item in proposal[key]:
            fields(item, gap_fields)
            if type(item["goal_refs"]) is not list or type(item["record_refs"]) is not list:
                raise ContractError("invalid_array", key + ".refs")
            for ref in item["goal_refs"]:
                fields(ref, {"type", "requirement_id", "revision", "task_version"})
            for ref in item["record_refs"]:
                fields(ref, {"type", "record_id", "revision"})
    focus = proposal["focus"]
    if type(focus) is not dict or focus.get("op") not in {"keep", "set", "clear"}:
        raise ContractError("invalid_focus_operation")
    fields(focus, {"op"} if focus["op"] == "keep" else
           {"op", "value"} if focus["op"] == "set" else {"op", "reason"})
    if focus["op"] == "set":
        fields(focus["value"], {"gap_ref", "reason", "changed_at_step"})
        fields(focus["value"]["gap_ref"], {"type", "gap_id", "revision",
                                           "task_version"})
    return proposal


def _local_id_map(proposal: dict, cycle_id: str) -> dict[str, str]:
    mapping = {}
    fields_to_scan = [(proposal["world_patch"]["entity_upserts"], "entity_id", "entity"),
                      (proposal["world_patch"]["state_upserts"], "record_id", "state"),
                      (proposal["world_patch"]["relation_upserts"], "relation_id", "relation"),
                      (proposal["specification_upserts"], "requirement_id", "requirement"),
                      (proposal["gap_upserts"], "gap_id", "gap")]
    for items, field, kind in fields_to_scan:
        for item in items:
            identifier = item.get(field)
            if type(identifier) is str and identifier.startswith("@"):
                if identifier in mapping:
                    raise ContractError("duplicate_local_id", identifier)
                mapping[identifier] = f"{kind}-{digest([cycle_id, identifier])[:20]}"
    return mapping


def _replace_local_ids(value: object, mapping: dict[str, str]) -> object:
    if type(value) is list:
        return [_replace_local_ids(item, mapping) for item in value]
    if type(value) is dict:
        result = {}
        for key, item in value.items():
            if key in {"entity_id", "record_id", "relation_id", "requirement_id",
                       "gap_id", "from_entity_id", "to_entity_id"} and (
                           type(item) is str and item in mapping):
                result[key] = mapping[item]
            elif key == "entity_ids" and type(item) is list:
                result[key] = [mapping.get(member, member) if type(member) is str
                               else member for member in item]
            else:
                result[key] = _replace_local_ids(item, mapping)
        return result
    return value


def _wire_to_internal(value: object, catalog: SourceCatalog) -> object:
    if type(value) is list:
        return [_wire_to_internal(item, catalog) for item in value]
    if type(value) is dict:
        if set(value) == {"evidence_id", "quote"}:
            return catalog.resolve(value, purpose="maintenance")
        if set(value) == {"source_id", "start", "end", "quote"}:
            raise ContractError("stored_ref_in_wire_proposal")
        return {key: _wire_to_internal(item, catalog) for key, item in value.items()}
    return value


def _upsert(items: list[dict], item: dict, key: str, *,
            archive_delta: list, kind: str,
            visible_existing_ids: set[tuple[str, str]],
            require_supersedes: bool = False) -> None:
    identifier = nonempty(item.get(key), key)
    for index, old in enumerate(items):
        if old[key] != identifier:
            continue
        if (kind, identifier) not in visible_existing_ids:
            raise ContractError("invisible_existing_object", identifier)
        if "revision" in old:
            if item.get("revision") != old["revision"] + 1:
                raise ContractError("version_mismatch", identifier)
            if require_supersedes and {"type": "state", "record_id": identifier,
                    "revision": old["revision"]} not in item.get("supersedes", []):
                raise ContractError("missing_direct_supersedes", identifier)
            archive_delta.append((kind, identifier, old["revision"], deepcopy(old)))
        elif key == "entity_id" and old["entity_type"] != item["entity_type"]:
            raise ContractError("entity_type_changed", identifier)
        items[index] = item
        return
    if "revision" in item and item["revision"] != 1:
        raise ContractError("new_object_revision", identifier)
    items.append(item)


def build_candidate(*, proposal: dict, base: dict, catalog: SourceCatalog,
                    cycle_id: str, processed_to: int, goal_ledger: dict,
                    visible_existing_ids: set[tuple[str, str]], archive: dict) -> dict:
    """Build once from base. Repair calls this again with a replacement proposal."""
    validate_proposal(proposal, request_id=proposal["request_id"],
                      task_version=goal_ledger["epoch"],
                      base_version=base["state_version"])
    mapping = _local_id_map(proposal, cycle_id)
    existing = {kind: {item[key] for item in items} for kind, items, key in (
        ("entity", base["B"]["W"]["entities"], "entity_id"),
        ("state", base["B"]["W"]["states"], "record_id"),
        ("relation", base["B"]["W"]["relations"], "relation_id"),
        ("requirement", base["B"]["G"]["specifications"], "requirement_id"),
        ("gap", base["B"]["DeltaE"] + base["B"]["DeltaA"], "gap_id"))}
    if len(set(mapping.values())) != len(mapping) or any(value in identifiers
            for value in mapping.values() for identifiers in existing.values()):
        raise ContractError("local_id_collision")
    for kind, items, key in (("entity", proposal["world_patch"]["entity_upserts"], "entity_id"),
                             ("state", proposal["world_patch"]["state_upserts"], "record_id"),
                             ("relation", proposal["world_patch"]["relation_upserts"], "relation_id"),
                             ("requirement", proposal["specification_upserts"], "requirement_id"),
                             ("gap", proposal["gap_upserts"], "gap_id")):
        for item in items:
            if item[key] not in existing[kind] and item[key] not in mapping:
                raise ContractError("new_object_requires_local_id", item[key])
    patch = _wire_to_internal(_replace_local_ids(proposal, mapping), catalog)
    new_ids = {("entity", item["entity_id"]) for item in patch["world_patch"][
        "entity_upserts"] if item["entity_id"] not in {old["entity_id"] for old in
        base["B"]["W"]["entities"]}}
    new_ids.update(("state", item["record_id"]) for item in patch["world_patch"][
        "state_upserts"] if item["record_id"] not in {old["record_id"] for old in
        base["B"]["W"]["states"]})
    new_ids.update(("requirement", item["requirement_id"]) for item in patch[
        "specification_upserts"] if item["requirement_id"] not in {old[
            "requirement_id"] for old in base["B"]["G"]["specifications"]})
    new_ids.update(("gap", item["gap_id"]) for item in patch["gap_upserts"] if
        item["gap_id"] not in {old["gap_id"] for old in base["B"]["DeltaE"] +
                               base["B"]["DeltaA"]})
    known_ids = {(kind, item[key]) for kind, items, key in (
        ("entity", base["B"]["W"]["entities"], "entity_id"),
        ("state", base["B"]["W"]["states"], "record_id"),
        ("requirement", base["B"]["G"]["specifications"], "requirement_id"),
        ("gap", base["B"]["DeltaE"] + base["B"]["DeltaA"], "gap_id"))
        for item in items}
    def require_visible(kind: str, identifier: str) -> None:
        identifier = nonempty(identifier, kind + "_id")
        identity = (kind, identifier)
        if identity in known_ids and identity not in visible_existing_ids:
            raise ContractError("invisible_existing_reference", identifier)
        if identity not in known_ids and identity not in new_ids:
            raise ContractError("unknown_reference", identifier)
    for item in patch["world_patch"]["state_upserts"]:
        require_visible("entity", item["entity_id"])
    for item in patch["world_patch"]["relation_upserts"]:
        require_visible("entity", item["from_entity_id"])
        require_visible("entity", item["to_entity_id"])
        require_visible("state", item["anchored_by"]["record_id"])
    for item in [*patch["gap_upserts"], *patch["gap_resolutions"],
                 *patch["gap_reopens"]]:
        for ref in item["goal_refs"]:
            require_visible("requirement", ref["requirement_id"])
        for ref in item["record_refs"]:
            require_visible("state", ref["record_id"])
    if patch["focus"]["op"] == "set":
        require_visible("gap", patch["focus"]["value"]["gap_ref"]["gap_id"])
    candidate = deepcopy(base)
    candidate["state_version"] += 1
    candidate["committed_event_seq"] = integer(processed_to, "processed_to")
    belief = candidate["B"]
    goal = belief["G"]
    goal["task_version"] = goal_ledger["epoch"]
    goal["goal_deltas"] = list(goal_ledger["deltas"].values())
    ledger = catalog.ledger
    for source_id in goal_ledger["messages"]:
        leaf = ledger[source_id]
        ref = {"source_id": source_id, "start": 0,
               "end": len(leaf["text"]), "quote": leaf["text"]}
        if ref not in goal["original_user_sources"]:
            goal["original_user_sources"].append(ref)
    world = belief["W"]
    archive_delta = []
    for item in patch["world_patch"]["entity_upserts"]:
        _upsert(world["entities"], item, "entity_id", archive_delta=archive_delta,
                kind="entity", visible_existing_ids=visible_existing_ids)
    for item in patch["world_patch"]["state_upserts"]:
        _upsert(world["states"], item, "record_id", archive_delta=archive_delta,
                kind="state", visible_existing_ids=visible_existing_ids,
                require_supersedes=True)
    for transition in patch["world_patch"]["record_transitions"]:
        fields(transition, {"record_ref", "to_status", "reason", "evidence_refs"})
        ref = transition["record_ref"]
        refs(transition["evidence_refs"], ledger)
        old = next((item for item in world["states"] if item["record_id"] ==
                    ref["record_id"]), None)
        if old is None or old["revision"] != ref["revision"]:
            raise ContractError("version_mismatch", ref["record_id"])
        new = deepcopy(old)
        new["revision"] += 1
        new["use_status"] = transition["to_status"]
        new["supersedes"].append(ref)
        _upsert(world["states"], new, "record_id", archive_delta=archive_delta,
                kind="state", visible_existing_ids=visible_existing_ids,
                require_supersedes=True)
    for item in patch["world_patch"]["relation_upserts"]:
        _upsert(world["relations"], item, "relation_id", archive_delta=archive_delta,
                kind="relation", visible_existing_ids=visible_existing_ids)
    for item in patch["specification_upserts"]:
        _upsert(goal["specifications"], item, "requirement_id",
                archive_delta=archive_delta, kind="requirement",
                visible_existing_ids=visible_existing_ids)
    for key in ("gap_upserts", "gap_resolutions", "gap_reopens"):
        for item in patch[key]:
            if (key == "gap_upserts" and item.get("status") not in {"open", "blocked"}
                    or key == "gap_resolutions" and item.get("status") not in
                    {"supported", "superseded"}
                    or key == "gap_reopens" and item.get("status") not in
                    {"open", "blocked"}):
                raise ContractError("gap_operation_status", key)
            lane = "DeltaE" if item["gap_kind"] == "epistemic" else "DeltaA"
            prior = next((gap for gap in belief[lane] if gap["gap_id"] ==
                          item["gap_id"]), None)
            if key == "gap_upserts" and prior is not None and prior["status"] not in {
                    "open", "blocked"}:
                raise ContractError("gap_upsert_requires_open_base")
            if key == "gap_resolutions" and (prior is None or prior["status"] not in {
                    "open", "blocked"}):
                raise ContractError("gap_resolution_requires_open_base")
            if key == "gap_reopens" and (prior is None or prior["status"] not in {
                    "supported", "superseded"}):
                raise ContractError("gap_reopen_requires_closed_base")
            _upsert(belief[lane], item, "gap_id", archive_delta=archive_delta,
                    kind="gap", visible_existing_ids=visible_existing_ids)
    focus = patch["focus"]
    if focus["op"] == "set":
        belief["F"] = focus["value"]
    elif focus["op"] == "clear":
        belief["F"] = None
    combined_archive = dict(archive)
    combined_archive.update({(identifier, revision) if kind == "state" else
        (kind, identifier, revision): body for kind, identifier, revision, body
        in archive_delta})
    validate_snapshot(candidate, ledger, combined_archive, goal_ledger["deltas"])
    update_id = "update-" + digest([cycle_id, proposal["request_id"],
                                     base["state_version"], digest(candidate)])[:24]
    return {"update_id": update_id, "base": base, "candidate": candidate,
            "canonical_patch": patch, "local_id_map": mapping,
            "archive_delta": archive_delta,
            "candidate_hash": digest(candidate)}
