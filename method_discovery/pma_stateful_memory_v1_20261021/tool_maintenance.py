"""Offline role-tool compiler, not a persistence or semantic acceptance gate.

The host supplies a frozen engine binding and its original base snapshot. The
result MUST still pass build_candidate with the original source catalog,
visibility set, goal ledger and archive. In particular this module cannot prove
source quotes/roles, historical-reference existence, or working-set visibility.
No host IO, model calls, candidate mutation, or implicit source/scope defaults.
"""
from copy import deepcopy

from .proposal import validate_proposal
from .source import ContractError, digest, fields, integer, nonempty
from .tool_native import NativeToolError, validate_tool_arguments


def _obj(**properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def _enum(*values):
    return {"type": "string", "enum": list(values)}


def _arr(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def _union(*schemas):
    return {"anyOf": list(schemas)}


_TEXT = {"type": "string", "minLength": 1}
_ZERO = {"type": "integer", "minimum": 0}
_ONE = {"type": "integer", "minimum": 1}
_NULL = {"type": "null"}
_SOURCE = _obj(evidence_id=_TEXT, quote=_TEXT)
_STATE = _obj(type=_enum("state"), record_id=_TEXT, revision=_ONE)
_REQUIREMENT = _obj(type=_enum("requirement"), requirement_id=_TEXT,
                    revision=_ONE, task_version=_ONE)
_GAP = _obj(type=_enum("gap"), gap_id=_TEXT, revision=_ONE, task_version=_ONE)
_DELTA = _obj(type=_enum("goal_delta"), goal_delta_id=_TEXT,
              from_task_version=_ONE, to_task_version={"type": "integer", "minimum": 2})
_CLAIM = _obj(text=_TEXT, assertion_origin=_enum("user_requirement", "user_report",
    "tool_observation", "agent_report", "inference"),
    time_role=_enum("present_fact", "past_episode", "general_hypothesis"),
    support_refs=_arr(_SOURCE), challenge_refs=_arr(_SOURCE))
_SCOPE = _obj(task_id=_TEXT, entity_ids=_arr(_TEXT, 1), conditions=_arr(_TEXT))
_RETIREMENT = _union(_NULL, _obj(kind=_enum("goal_changed"), goal_delta_ref=_DELTA),
    _obj(kind=_enum("interpretation_replaced"),
         replacement_requirement_refs=_arr(_REQUIREMENT, 1), source_refs=_arr(_SOURCE, 1)))
_CLOSURE = _union(_NULL,
    _obj(kind=_enum("environment_supported"), conclusion=_TEXT,
         evidence_refs=_arr(_SOURCE, 1), state_refs=_arr(_STATE)),
    _obj(kind=_enum("goal_changed"), goal_delta_ref=_DELTA),
    _obj(kind=_enum("merged_into"), replacement_gap_ref=_GAP))
_COMMON_STATE = dict(record_id=_TEXT, entity_id=_TEXT, scope=_SCOPE,
    use_status=_enum("active", "historical_only", "contested", "retracted"),
    updated_at_step=_ZERO, supersedes=_arr(_STATE))
_COMMON_GAP = dict(gap_id=_TEXT, task_version=_ONE,
    gap_kind=_enum("epistemic", "achievement"), target=_TEXT, reason=_TEXT,
    goal_refs=_arr(_REQUIREMENT, 1), record_refs=_arr(_STATE),
    status=_enum("open", "blocked"), closure=_NULL)
_SCHEMAS = {
    "propose_knowledge": _obj(**_COMMON_STATE, claim=_CLAIM),
    "propose_experience": _obj(**_COMMON_STATE, episode=_obj(
        conditions=_CLAIM, action_text=_TEXT, action_refs=_arr(_SOURCE, 1),
        result=_CLAIM, time_role=_enum("past_episode")), lesson=_union(_NULL, _CLAIM)),
    "transition_record": _obj(record_ref=_STATE,
        to_status=_enum("historical_only", "contested", "retracted"),
        reason=_TEXT, evidence_refs=_arr(_SOURCE)),
    "put_entity": _obj(entity_id=_TEXT,
        entity_type=_enum("file", "function", "tool", "environment", "artifact", "attempt", "other"),
        display_name=_TEXT),
    "put_relation": _obj(relation_id=_TEXT, from_entity_id=_TEXT,
        to_entity_id=_TEXT, predicate=_TEXT, anchored_by=_STATE),
    "put_requirement": _obj(requirement_id=_TEXT, task_version=_ONE,
        interpretation=_TEXT, source_refs=_arr(_SOURCE, 1),
        status=_enum("active", "superseded"), retirement=_RETIREMENT),
    "open_gap": _obj(**_COMMON_GAP),
    "revise_gap": _obj(**_COMMON_GAP),
    "resolve_gap": _obj(**{**_COMMON_GAP,
        "status": _enum("supported", "superseded"), "closure": _CLOSURE}),
    "reopen_gap": _obj(**_COMMON_GAP),
    "set_focus": _obj(gap_ref=_GAP, reason=_TEXT, changed_at_step=_ZERO),
    "clear_focus": _obj(reason=_TEXT),
    "memory_no_change": _obj(),
}
_DESCRIPTIONS = {
    "propose_knowledge": "Propose one knowledge record. Use @local for new records; revisions are host-derived. Preserve explicit scope, provenance and supersedes refs.",
    "propose_experience": "Propose one past procedural episode with an optional inferential lesson; not a present fact.",
    "transition_record": "Change one exact current state reference's use status, with reason and evidence.",
    "put_entity": "Name or rename a typed entity; never store facts as entity attributes.",
    "put_relation": "Propose one relation anchored by an explicit state revision, including historical revisions.",
    "put_requirement": "Propose a requirement interpretation or retirement; preserve its semantic task epoch and provenance.",
    "open_gap": "Open one new @local epistemic or achievement gap tied to requirements.",
    "revise_gap": "Revise one currently open or blocked gap; supply the complete replacement meaning.",
    "resolve_gap": "Resolve an existing open gap with supported or superseded status and explicit closure.",
    "reopen_gap": "Reopen a supported or superseded gap with a complete current interpretation.",
    "set_focus": "Select an explicit open gap revision as focus, with reason and step.",
    "clear_focus": "Clear focus with an explicit reason.",
    "memory_no_change": "Explicitly propose no maintenance changes. Must be the only call.",
}


def tool_definitions():
    """Return fresh Chat Completions function descriptors (no execution hooks)."""
    return [{"type": "function", "function": {"name": name,
        "description": _DESCRIPTIONS[name], "parameters": deepcopy(schema)}}
        for name, schema in _SCHEMAS.items()]


def _validated(arguments, schema):
    try:
        return validate_tool_arguments(arguments, schema)
    except NativeToolError as error:
        raise ContractError("tool_argument_schema", error.code) from error


def _check_claim(item):
    if item["assertion_origin"] == "inference":
        if item["time_role"] != "general_hypothesis":
            raise ContractError("inference_time_role")
    elif not item["support_refs"]:
        raise ContractError("missing_source_ref")


def _check_semantics(name, item, *, epoch, task_id):
    """Local cross-field contracts; source and graph checks remain host-owned."""
    if name in {"propose_knowledge", "propose_experience"}:
        scope = item["scope"]
        if scope["task_id"] != task_id:
            raise ContractError("scope_task_mismatch")
        if len(set(scope["entity_ids"])) != len(scope["entity_ids"]):
            raise ContractError("duplicate_id", "scope.entity_ids")
        edges = [(edge["record_id"], edge["revision"]) for edge in item["supersedes"]]
        if len(set(edges)) != len(edges):
            raise ContractError("supersedes_cycle_or_duplicate")
        if name == "propose_knowledge":
            _check_claim(item["claim"])
        else:
            for key in ("conditions", "result"):
                claim = item["episode"][key]
                _check_claim(claim)
                if claim["time_role"] != "past_episode":
                    raise ContractError("episode_claim_time_role")
            lesson = item["lesson"]
            if lesson is not None:
                _check_claim(lesson)
                if lesson["assertion_origin"] != "inference" or lesson["time_role"] != "general_hypothesis":
                    raise ContractError("lesson_origin_or_time_role")
                if not lesson["support_refs"]:
                    raise ContractError("lesson_missing_support")
    if name == "put_requirement":
        if item["status"] == "active":
            if item["retirement"] is not None or item["task_version"] != epoch:
                raise ContractError("active_requirement_version")
        elif item["retirement"] is None:
            raise ContractError("missing_retirement")
    if name in {"open_gap", "revise_gap", "reopen_gap"} and item["task_version"] != epoch:
        raise ContractError("open_gap_contract")
    if name == "resolve_gap":
        closure = item["closure"]
        if closure is None:
            raise ContractError("missing_gap_closure")
        kinds = {"environment_supported"} if item["status"] == "supported" else {"goal_changed", "merged_into"}
        if closure["kind"] not in kinds:
            raise ContractError("gap_closure_kind")


def compile_maintenance(calls, *, binding, base):
    """Compile one complete normalized batch, atomically and without side effects.

    `calls` is a nonempty list of {name, arguments: object}; native call IDs and
    JSON decoding belong to the transport normalizer. `binding` is the existing
    engine maintenance binding (never tool-supplied). Existing mutation targets
    must be in base; archive-capable historical refs are deferred to the mandatory
    build_candidate gate, as is actual working-set visibility.
    Historical refs and semantic epochs/timestamps are never silently upgraded.
    """
    if type(calls) is not list or not calls:
        raise ContractError("empty_maintenance_calls")
    # Validate/detach the entire batch first. Even an unknown later call or a
    # Python-only value fails atomically before domain compilation begins.
    calls = _validated({"calls": calls}, _obj(calls=_arr(
        _obj(name=_TEXT, arguments={"type": "object"}), 1)))["calls"]
    if type(binding) is not dict:
        raise ContractError("invalid_binding")
    request = nonempty(binding.get("request_id"), "request_id")
    epoch = integer(binding.get("active_task_version"), "active_task_version", 1)
    version = integer(binding.get("base_state_version"), "base_state_version")
    if version != base["state_version"] or ("base_state_hash" in binding and
            binding["base_state_hash"] != digest(base)):
        raise ContractError("version_mismatch")
    for key in ("task_id", "episode_id"):
        if key in binding and binding[key] != base[key]:
            raise ContractError("binding_mismatch", key)
    proposal = {"protocol": "maintenance-proposal/1", "request_id": request,
        "active_task_version": epoch, "base_state_version": version,
        "world_patch": {"entity_upserts": [], "state_upserts": [],
                        "relation_upserts": [], "record_transitions": []},
        "specification_upserts": [], "gap_upserts": [], "gap_resolutions": [],
        "gap_reopens": [], "focus": {"op": "keep"}}
    groups = {
        "entity": (base["B"]["W"]["entities"], "entity_id"),
        "state": (base["B"]["W"]["states"], "record_id"),
        "relation": (base["B"]["W"]["relations"], "relation_id"),
        "requirement": (base["B"]["G"]["specifications"], "requirement_id"),
        "gap": (base["B"]["DeltaE"] + base["B"]["DeltaA"], "gap_id")}
    heads = {kind: {item[key]: item for item in items}
             for kind, (items, key) in groups.items()}
    local = {}
    focus_seen = False
    routes = {"put_entity": ("entity", "entity_upserts"),
              "put_relation": ("relation", "relation_upserts"),
              "propose_knowledge": ("state", "state_upserts"),
              "propose_experience": ("state", "state_upserts"),
              "put_requirement": ("requirement", "specification_upserts"),
              "open_gap": ("gap", "gap_upserts"),
              "revise_gap": ("gap", "gap_upserts"),
              "resolve_gap": ("gap", "gap_resolutions"),
              "reopen_gap": ("gap", "gap_reopens")}
    for call in calls:
        fields(call, {"name", "arguments"})
        name = nonempty(call["name"], "tool.name")
        if name not in _SCHEMAS:
            raise ContractError("unknown_maintenance_tool", name)
        item = _validated(call["arguments"], _SCHEMAS[name])
        _check_semantics(name, item, epoch=epoch, task_id=base["task_id"])
        if name == "memory_no_change":
            if len(calls) != 1:
                raise ContractError("no_change_must_be_exclusive")
            continue
        if name in {"set_focus", "clear_focus"}:
            if focus_seen:
                raise ContractError("conflicting_operations", "focus")
            focus_seen = True
            proposal["focus"] = ({"op": "set", "value": item} if name == "set_focus"
                                 else {"op": "clear", "reason": item["reason"]})
            continue
        if name == "transition_record":
            ref = item["record_ref"]
            prior = heads["state"].get(ref["record_id"])
            if prior is None or prior["revision"] != ref["revision"]:
                raise ContractError("version_mismatch", ref["record_id"])
            proposal["world_patch"]["record_transitions"].append(item)
            continue
        kind, route = routes[name]
        key = groups[kind][1]
        identifier = item[key]
        prior = heads[kind].get(identifier)
        if prior is None:
            if not identifier.startswith("@") or len(identifier) == 1:
                raise ContractError("new_object_requires_local_id", identifier)
            if identifier in local or any(identifier in values for values in heads.values()):
                raise ContractError("duplicate_local_id", identifier)
            local[identifier] = kind
        if kind in {"state", "requirement", "gap"}:
            item["revision"] = prior["revision"] + 1 if prior is not None else 1
        if kind == "state":
            item["kind"] = "knowledge" if name == "propose_knowledge" else "procedural"
            if prior is not None and {"type": "state", "record_id": identifier,
                    "revision": prior["revision"]} not in item["supersedes"]:
                raise ContractError("missing_direct_supersedes", identifier)
        if kind == "entity" and prior and prior["entity_type"] != item["entity_type"]:
            raise ContractError("entity_type_changed", identifier)
        if kind == "gap":
            if (name == "open_gap") != (prior is None):
                raise ContractError("gap_operation_base", name)
            if prior is not None:
                allowed = {"supported", "superseded"} if name == "reopen_gap" else {"open", "blocked"}
                if prior["status"] not in allowed or prior["gap_kind"] != item["gap_kind"]:
                    raise ContractError("gap_operation_base", name)
        target = proposal["world_patch"] if route in proposal["world_patch"] else proposal
        target[route].append(item)

    def known(kind, identifier):
        if identifier not in heads[kind] and local.get(identifier) != kind:
            raise ContractError("unknown_reference", kind + ":" + identifier)

    def check_refs(value, *, historical=False):
        if type(value) is list:
            for member in value:
                check_refs(member, historical=historical)
        elif type(value) is dict:
            if value.get("type") in {"state", "requirement", "gap"}:
                kind = value["type"]
                identifier = value[groups[kind][1]]
                # These exact historical refs may exist only in the archive,
                # which this compiler intentionally does not receive. Never
                # manufacture a current head or erase their old revisions.
                if not historical or identifier.startswith("@"):
                    known(kind, identifier)
            for key, member in value.items():
                if key in {"entity_id", "from_entity_id", "to_entity_id"}:
                    known("entity", member)
                elif key == "entity_ids":
                    for identifier in member:
                        known("entity", identifier)
                else:
                    check_refs(member, historical=key in {
                        "supersedes", "state_refs", "replacement_requirement_refs"})
    check_refs(proposal)
    return validate_proposal(proposal, request_id=request,
                             task_version=epoch, base_version=version)
