"""Strict stored-state contracts; semantic truth remains a model judgment."""

from __future__ import annotations

from .source import ContractError, canonical, fields, integer, nonempty, validate_source_ref


def array(value: object, name: str) -> list:
    if type(value) is not list:
        raise ContractError("invalid_array", name)
    return value


def enum(value: object, choices: set[str], name: str) -> str:
    if type(value) is not str or value not in choices:
        raise ContractError("invalid_enum", name)
    return value


def unique(values: list[str], name: str) -> None:
    if len(set(values)) != len(values):
        raise ContractError("duplicate_id", name)


def refs(value: object, ledger: dict, kinds: set[str] | None = None,
         *, required: bool = False) -> list:
    result = array(value, "source_refs")
    if required and not result:
        raise ContractError("missing_source_ref")
    for item in result:
        validate_source_ref(item, ledger, allowed_kinds=kinds)
    return result


def state_ref(value: object, heads: dict[str, dict], archive: dict,
              *, historical: bool = False) -> dict:
    ref = fields(value, {"type", "record_id", "revision"})
    if ref["type"] != "state":
        raise ContractError("invalid_state_ref")
    record_id = nonempty(ref["record_id"], "record_id")
    revision = integer(ref["revision"], "revision", 1)
    head = heads.get(record_id)
    if head is not None and head["revision"] == revision:
        return ref
    if historical and (record_id, revision) in archive:
        return ref
    raise ContractError("version_mismatch", record_id)


def requirement_ref(value: object, requirements: dict[str, dict], archive: dict | None = None,
                    *, historical: bool = False) -> dict:
    ref = fields(value, {"type", "requirement_id", "revision", "task_version"})
    if ref["type"] != "requirement":
        raise ContractError("invalid_requirement_ref")
    item = requirements.get(nonempty(ref["requirement_id"], "requirement_id"))
    integer(ref["revision"], "revision", 1)
    integer(ref["task_version"], "task_version", 1)
    if item is not None and (item["revision"], item["task_version"]) == (
            ref["revision"], ref["task_version"]):
        return ref
    old = (archive or {}).get(("requirement", ref["requirement_id"], ref["revision"]))
    if historical and old is not None and old["task_version"] == ref["task_version"]:
        return ref
    raise ContractError("version_mismatch", ref["requirement_id"])


def validate_requirement_retirement_transition(base: dict, candidate: dict,
                                               archive: dict, goal_ledger: dict) -> None:
    """New relationships target current heads; unchanged ones retain history."""
    if candidate["B"]["G"]["task_version"] != goal_ledger["epoch"]:
        raise ContractError("goal_epoch_mismatch")
    old = {item["requirement_id"]: item for item in base["B"]["G"][
        "specifications"]}
    current = {item["requirement_id"]: item for item in candidate["B"]["G"][
        "specifications"]}
    for identifier, item in current.items():
        retirement = item["retirement"]
        if not retirement or retirement["kind"] != "interpretation_replaced":
            continue
        prior = old.get(identifier)
        unchanged = (prior is not None and prior["status"] == "superseded" and
            prior["retirement"] is not None and canonical(prior["retirement"]) ==
            canonical(retirement))
        if unchanged:
            continue
        for ref in retirement["replacement_requirement_refs"]:
            replacement = current.get(ref["requirement_id"])
            if (replacement is None or replacement["status"] != "active" or
                    replacement["revision"] != ref["revision"] or
                    replacement["task_version"] != ref["task_version"] or
                    replacement["task_version"] != goal_ledger["epoch"]):
                raise ContractError("invalid_requirement_replacement")
    graph = {}
    for item in [*current.values(), *(body for key, body in archive.items() if
                 len(key) == 3 and key[0] == "requirement")]:
        retirement = item["retirement"]
        if retirement and retirement["kind"] == "interpretation_replaced":
            graph.setdefault(item["requirement_id"], set()).update(ref[
                "requirement_id"] for ref in retirement["replacement_requirement_refs"])
    active, done = set(), set()
    def visit(identifier):
        if identifier in active:
            raise ContractError("requirement_replacement_cycle")
        if identifier in done:
            return
        active.add(identifier)
        for target in graph.get(identifier, ()):
            visit(target)
        active.remove(identifier)
        done.add(identifier)
    for identifier in graph:
        visit(identifier)


def gap_ref(value: object, gaps: dict[str, dict]) -> dict:
    ref = fields(value, {"type", "gap_id", "revision", "task_version"})
    if ref["type"] != "gap":
        raise ContractError("invalid_gap_ref")
    item = gaps.get(nonempty(ref["gap_id"], "gap_id"))
    integer(ref["revision"], "revision", 1)
    integer(ref["task_version"], "task_version", 1)
    if item is None or (item["revision"], item["task_version"]) != (
            ref["revision"], ref["task_version"]):
        raise ContractError("version_mismatch", ref["gap_id"])
    return ref


def goal_delta_ref(value: object, deltas: dict[str, dict]) -> dict:
    ref = fields(value, {"type", "goal_delta_id", "from_task_version",
                         "to_task_version"})
    if ref["type"] != "goal_delta":
        raise ContractError("invalid_goal_delta")
    integer(ref["from_task_version"], "from_task_version", 1)
    integer(ref["to_task_version"], "to_task_version", 2)
    if ref["to_task_version"] <= ref["from_task_version"]:
        raise ContractError("invalid_goal_delta")
    if deltas.get(ref["goal_delta_id"]) != ref:
        raise ContractError("unknown_goal_delta")
    return ref


def claim(value: object, ledger: dict) -> dict:
    item = fields(value, {"text", "assertion_origin", "time_role",
                          "support_refs", "challenge_refs"})
    nonempty(item["text"], "claim.text")
    origin = enum(item["assertion_origin"], {"user_requirement", "user_report",
        "tool_observation", "agent_report", "inference"}, "assertion_origin")
    role = enum(item["time_role"], {"present_fact", "past_episode",
                                "general_hypothesis"}, "time_role")
    source_kinds = {
        "user_requirement": {"user_requirement"},
        "user_report": {"user_report"},
        "tool_observation": {"tool_result"},
        "agent_report": {"agent_report"},
    }
    support = refs(item["support_refs"], ledger, source_kinds.get(origin),
                   required=origin != "inference")
    refs(item["challenge_refs"], ledger)
    if origin == "inference" and role != "general_hypothesis":
        raise ContractError("inference_time_role")
    if origin != "inference" and not support:
        raise ContractError("missing_source_ref")
    return item


def scope(value: object, task_id: str, entity_ids: set[str]) -> dict:
    item = fields(value, {"task_id", "entity_ids", "conditions"})
    if item["task_id"] != task_id:
        raise ContractError("scope_task_mismatch")
    ids = array(item["entity_ids"], "entity_ids")
    if not ids or any(type(value) is not str or value not in entity_ids for value in ids):
        raise ContractError("unknown_scope_entity")
    unique(ids, "scope.entity_ids")
    for condition in array(item["conditions"], "conditions"):
        nonempty(condition, "scope.condition")
    return item


def validate_snapshot(snapshot: object, ledger: dict[str, dict],
                      archive: dict[tuple[str, int], dict] | None = None,
                      goal_deltas: dict[str, dict] | None = None) -> dict:
    """Validate closed-world structure and cross-references, not proposition truth."""
    archive = archive or {}
    goal_deltas = goal_deltas or {}
    snap = fields(snapshot, {"schema_version", "task_id", "episode_id",
                             "state_version", "committed_event_seq", "B"})
    if snap["schema_version"] != "stateful-proactive-memory/1":
        raise ContractError("schema_version")
    task_id = nonempty(snap["task_id"], "task_id")
    nonempty(snap["episode_id"], "episode_id")
    state_version = integer(snap["state_version"], "state_version")
    integer(snap["committed_event_seq"], "committed_event_seq")
    belief = fields(snap["B"], {"G", "W", "DeltaE", "DeltaA", "F"})
    goal = fields(belief["G"], {"task_version", "original_user_sources",
                                "specifications", "goal_deltas"})
    task_version = integer(goal["task_version"], "task_version", 1)
    refs(goal["original_user_sources"], ledger, {"user_requirement"}, required=True)
    for delta in array(goal["goal_deltas"], "goal_deltas"):
        goal_delta_ref(delta, goal_deltas)
    requirements = {}
    for item in array(goal["specifications"], "specifications"):
        item = fields(item, {"requirement_id", "revision", "task_version",
                             "interpretation", "source_refs", "status", "retirement"})
        rid = nonempty(item["requirement_id"], "requirement_id")
        integer(item["revision"], "revision", 1)
        integer(item["task_version"], "task_version", 1)
        nonempty(item["interpretation"], "interpretation")
        refs(item["source_refs"], ledger, {"user_requirement"}, required=True)
        enum(item["status"], {"active", "superseded"}, "requirement.status")
        if rid in requirements:
            raise ContractError("duplicate_id", rid)
        requirements[rid] = item
    for item in requirements.values():
        retirement = item["retirement"]
        if item["status"] == "active":
            if retirement is not None or item["task_version"] != task_version:
                raise ContractError("active_requirement_version")
        else:
            if type(retirement) is not dict:
                raise ContractError("missing_retirement")
            kind = retirement.get("kind")
            if kind == "goal_changed":
                fields(retirement, {"kind", "goal_delta_ref"})
                delta = goal_delta_ref(retirement["goal_delta_ref"], goal_deltas)
                if delta["from_task_version"] != item["task_version"] or delta[
                        "to_task_version"] > task_version:
                    raise ContractError("retirement_goal_delta_mismatch")
            elif kind == "interpretation_replaced":
                fields(retirement, {"kind", "replacement_requirement_refs", "source_refs"})
                refs(retirement["source_refs"], ledger, {"user_requirement"}, required=True)
                replacements = array(retirement["replacement_requirement_refs"],
                                     "replacement_requirement_refs")
                if not replacements:
                    raise ContractError("missing_requirement_replacement")
                for ref in replacements:
                    validated = requirement_ref(ref, requirements, archive,
                                                historical=True)
                    if validated["requirement_id"] == item["requirement_id"]:
                        raise ContractError("invalid_requirement_replacement")
            else:
                raise ContractError("invalid_retirement")
    world = fields(belief["W"], {"entities", "states", "relations"})
    entities = {}
    for item in array(world["entities"], "entities"):
        item = fields(item, {"entity_id", "entity_type", "display_name"})
        eid = nonempty(item["entity_id"], "entity_id")
        enum(item["entity_type"], {"file", "function", "tool", "environment",
                                  "artifact", "attempt", "other"}, "entity_type")
        nonempty(item["display_name"], "display_name")
        if eid in entities:
            raise ContractError("duplicate_id", eid)
        entities[eid] = item
    heads = {}
    for item in array(world["states"], "states"):
        item = fields(item, {"record_id", "revision", "entity_id", "scope",
                             "use_status", "updated_at_step", "supersedes", "kind"},
                      {"claim", "episode", "lesson"})
        record_id = nonempty(item["record_id"], "record_id")
        integer(item["revision"], "revision", 1)
        if item["entity_id"] not in entities or record_id in heads:
            raise ContractError("unknown_or_duplicate_state", record_id)
        scope(item["scope"], task_id, set(entities))
        enum(item["use_status"], {"active", "historical_only", "contested",
                                  "retracted"}, "use_status")
        integer(item["updated_at_step"], "updated_at_step")
        heads[record_id] = item
    for item in heads.values():
        if item["kind"] == "knowledge":
            fields(item, {"record_id", "revision", "entity_id", "scope",
                          "use_status", "updated_at_step", "supersedes", "kind", "claim"})
            claim(item["claim"], ledger)
        elif item["kind"] == "procedural":
            fields(item, {"record_id", "revision", "entity_id", "scope",
                          "use_status", "updated_at_step", "supersedes", "kind",
                          "episode", "lesson"})
            episode = fields(item["episode"], {"conditions", "action_text",
                                               "action_refs", "result", "time_role"})
            if episode["time_role"] != "past_episode":
                raise ContractError("episode_time_role")
            claim(episode["conditions"], ledger)
            claim(episode["result"], ledger)
            if (episode["conditions"]["time_role"] != "past_episode" or
                    episode["result"]["time_role"] != "past_episode"):
                raise ContractError("episode_claim_time_role")
            nonempty(episode["action_text"], "action_text")
            refs(episode["action_refs"], ledger, {"executed_action"}, required=True)
            if item["lesson"] is not None:
                lesson = fields(item["lesson"], {"text", "assertion_origin",
                                                 "time_role", "support_refs", "challenge_refs"})
                claim(lesson, ledger)
                if lesson["assertion_origin"] != "inference" or lesson[
                        "time_role"] != "general_hypothesis":
                    raise ContractError("lesson_origin_or_time_role")
                if not lesson["support_refs"]:
                    raise ContractError("lesson_missing_support")
        else:
            raise ContractError("invalid_state_kind")
        supersedes = array(item["supersedes"], "supersedes")
        seen_edges = set()
        for edge in supersedes:
            state_ref(edge, heads, archive, historical=True)
            identity = (edge["record_id"], edge["revision"])
            if identity == (item["record_id"], item["revision"]) or identity in seen_edges:
                raise ContractError("supersedes_cycle_or_duplicate")
            seen_edges.add(identity)
    relation_ids = set()
    for item in array(world["relations"], "relations"):
        item = fields(item, {"relation_id", "from_entity_id", "predicate",
                             "to_entity_id", "anchored_by"})
        relation_id = nonempty(item["relation_id"], "relation_id")
        if relation_id in relation_ids:
            raise ContractError("duplicate_id", relation_id)
        relation_ids.add(relation_id)
        if item["from_entity_id"] not in entities or item["to_entity_id"] not in entities:
            raise ContractError("unknown_relation_entity")
        nonempty(item["predicate"], "predicate")
        state_ref(item["anchored_by"], heads, archive, historical=True)
    history = {(record_id, item["revision"]): item for record_id, item in
               heads.items()}
    history.update({key: body for key, body in archive.items() if len(key) == 2})
    visited, active = set(), set()
    def check_supersedes(node):
        if node in active:
            raise ContractError("supersedes_cycle")
        if node in visited:
            return
        active.add(node)
        for edge in history[node]["supersedes"]:
            target = (edge["record_id"], edge["revision"])
            if target not in history:
                raise ContractError("version_mismatch", edge["record_id"])
            check_supersedes(target)
        active.remove(node)
        visited.add(node)
    for node in history:
        check_supersedes(node)
    gaps = {}
    for lane, kind in (("DeltaE", "epistemic"), ("DeltaA", "achievement")):
        for item in array(belief[lane], lane):
            item = fields(item, {"gap_id", "revision", "task_version", "gap_kind",
                                 "target", "reason", "goal_refs", "record_refs",
                                 "status", "closure"})
            gid = nonempty(item["gap_id"], "gap_id")
            if gid in gaps or item["gap_kind"] != kind:
                raise ContractError("duplicate_or_wrong_gap_kind", gid)
            integer(item["revision"], "revision", 1)
            integer(item["task_version"], "task_version", 1)
            nonempty(item["target"], "target")
            nonempty(item["reason"], "reason")
            if not array(item["goal_refs"], "goal_refs"):
                raise ContractError("gap_missing_goal")
            is_current = item["status"] in {"open", "blocked"}
            for ref in item["goal_refs"]:
                requirement_ref(ref, requirements, archive, historical=not is_current)
            for ref in array(item["record_refs"], "record_refs"):
                state_ref(ref, heads, archive, historical=True)
            enum(item["status"], {"open", "blocked", "supported", "superseded"},
                 "gap.status")
            gaps[gid] = item
    for item in gaps.values():
        closure = item["closure"]
        if item["status"] in {"open", "blocked"}:
            if closure is not None or item["task_version"] != task_version:
                raise ContractError("open_gap_contract")
            for ref in item["goal_refs"]:
                if requirements[ref["requirement_id"]]["status"] != "active" or (
                    requirements[ref["requirement_id"]]["task_version"] != task_version):
                    raise ContractError("open_gap_inactive_goal")
        elif type(closure) is not dict:
            raise ContractError("missing_gap_closure")
        elif item["status"] == "supported":
            closure = fields(closure, {"kind", "conclusion", "evidence_refs", "state_refs"})
            if closure["kind"] != "environment_supported":
                raise ContractError("gap_closure_kind")
            nonempty(closure["conclusion"], "conclusion")
            evidence = refs(closure["evidence_refs"], ledger,
                            {"tool_result", "user_report", "agent_report", "executed_action"},
                            required=True)
            if not any(ledger[ref["source_id"]]["source_kind"] in
                       {"tool_result", "user_report"} for ref in evidence):
                raise ContractError("closure_source_role")
            for ref in array(closure["state_refs"], "state_refs"):
                state_ref(ref, heads, archive, historical=True)
        elif closure.get("kind") == "goal_changed":
            fields(closure, {"kind", "goal_delta_ref"})
            goal_delta_ref(closure["goal_delta_ref"], goal_deltas)
        elif closure.get("kind") == "merged_into":
            fields(closure, {"kind", "replacement_gap_ref"})
            replacement = gap_ref(closure["replacement_gap_ref"], gaps)
            if replacement["gap_id"] == item["gap_id"]:
                raise ContractError("gap_merge_cycle")
        else:
            raise ContractError("gap_closure_kind")
    for item in gaps.values():
        chain, current = set(), item
        while current["status"] == "superseded" and current["closure"]["kind"] == "merged_into":
            if current["gap_id"] in chain:
                raise ContractError("gap_merge_cycle")
            chain.add(current["gap_id"])
            current = gaps[current["closure"]["replacement_gap_ref"]["gap_id"]]
    if belief["F"] is not None:
        focus = fields(belief["F"], {"gap_ref", "reason", "changed_at_step"})
        target = gaps[gap_ref(focus["gap_ref"], gaps)["gap_id"]]
        if target["status"] not in {"open", "blocked"}:
            raise ContractError("focus_not_open")
        nonempty(focus["reason"], "focus.reason")
        integer(focus["changed_at_step"], "changed_at_step")
    if state_version == 0 and (world["entities"] or world["states"] or
                               world["relations"] or goal["specifications"] or
                               belief["DeltaE"] or belief["DeltaA"] or belief["F"]):
        raise ContractError("nonempty_initial_snapshot")
    canonical(snap)
    return snap
