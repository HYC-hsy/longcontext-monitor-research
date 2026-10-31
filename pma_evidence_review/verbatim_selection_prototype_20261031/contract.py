"""Pure selection/presentation contract. Python 3.9+, standard library only."""
from __future__ import annotations
from dataclasses import dataclass
import json

CATEGORIES = frozenset({"knowledge", "procedural", "gap"})


class ContractError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ContractError(code)


def opaque_id(value):
    return type(value) is str and bool(value)


@dataclass(frozen=True)
class Item:
    id: str
    revision: str
    category: str
    text: str


@dataclass(frozen=True)
class Snapshot:
    cycle: str
    task_version: str
    task_text: str
    internal_status: str
    items: tuple[Item, ...]


def freeze_snapshot(cycle, task_version, task_text, internal_status,
                    committed_records):
    """Host adapter: records MUST come from the existing committed-store gate.

    This function checks structure, never semantic approval. The selector must
    have no way to supply records, task text, status, or approval booleans here.
    Caller holds the store lock/transaction while obtaining the source records.
    """
    require(opaque_id(cycle), "invalid_cycle")
    require(opaque_id(task_version), "invalid_task_version")
    require(type(task_text) is str and type(internal_status) is str,
            "invalid_host_text")
    items = []
    seen = set()
    for record in committed_records:
        require(type(record) is dict and
                set(record) == {"id", "revision", "category", "text"},
                "invalid_committed_record")
        i, rev, category, text = (record[k] for k in
                                  ("id", "revision", "category", "text"))
        require(opaque_id(i) and opaque_id(rev), "invalid_item_identity")
        require(type(category) is str and category in CATEGORIES,
                "invalid_category")
        require(type(text) is str, "invalid_item_text")
        require(i not in seen, "duplicate_committed_id")
        seen.add(i)
        items.append(Item(i, rev, category, text))
    return Snapshot(cycle, task_version, task_text, internal_status, tuple(items))


@dataclass(frozen=True)
class TaskRef:
    version: str


@dataclass(frozen=True)
class MemoryRef:
    id: str
    revision: str


@dataclass(frozen=True)
class Block:
    reference: TaskRef | MemoryRef
    text: str


@dataclass(frozen=True)
class Outcome:
    kind: str  # intervention | no_intervention | error
    blocks: tuple[Block, ...] = ()
    error: str | None = None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_):
    raise ContractError("invalid_json_constant")


def parse_and_render(raw, snapshot, *, active_cycle, active_task_version):
    """Validate selector output atomically; render only pinned snapshot text.

    Host must validate and dispatch under the same cycle/task lock. A live item
    edit/delete within that cycle does not revoke this snapshot: pinned content
    is delivered. To revoke it, host advances the active cycle first.
    """
    try:
        require(opaque_id(active_cycle) and opaque_id(active_task_version),
                "invalid_active_identity")
        require(snapshot.cycle == active_cycle and
                snapshot.task_version == active_task_version, "stale_snapshot")
        require(type(raw) is str, "output_not_string")
        data = json.loads(raw, object_pairs_hook=unique_object,
                          parse_constant=reject_constant)
        require(type(data) is dict and set(data) ==
                {"cycle", "task_version", "decision", "references"},
                "invalid_decision_fields")
        require(type(data["cycle"]) is str and data["cycle"] == snapshot.cycle,
                "wrong_cycle")
        require(opaque_id(data["task_version"]) and
                data["task_version"] == snapshot.task_version, "wrong_task_version")
        decision, refs = data["decision"], data["references"]
        require(type(decision) is str and decision in
                {"intervene", "no_intervention"}, "invalid_decision")
        require(type(refs) is list,
                "invalid_references")
        require((decision == "intervene" and bool(refs)) or
                (decision == "no_intervention" and not refs),
                "decision_selection_conflict")
        items = {item.id: item for item in snapshot.items}
        blocks = []
        seen = set()
        for ref in refs:
            require(type(ref) is dict, "invalid_reference")
            kind = ref.get("kind")
            require(type(kind) is str, "invalid_reference_kind")
            if kind == "task":
                require(set(ref) == {"kind", "version"}, "invalid_task_reference")
                require(opaque_id(ref["version"]) and
                        ref["version"] == snapshot.task_version,
                        "wrong_task_reference_version")
                typed = TaskRef(ref["version"])
                text = snapshot.task_text
            elif kind == "memory":
                require(set(ref) == {"kind", "id", "revision"},
                        "invalid_memory_reference")
                require(opaque_id(ref["id"]) and opaque_id(ref["revision"]),
                        "invalid_memory_identity")
                item = items.get(ref["id"])
                require(item is not None, "unknown_memory_id")
                require(item.revision == ref["revision"], "wrong_memory_revision")
                typed = MemoryRef(item.id, item.revision)
                text = item.text
            else:
                raise ContractError("unselectable_reference_kind")
            require(typed not in seen, "duplicate_reference")
            seen.add(typed)
            blocks.append(Block(typed, text))
        return Outcome("intervention" if blocks else "no_intervention",
                       tuple(blocks))
    except ContractError as exc:
        return Outcome("error", error=str(exc))
    except (ValueError, UnicodeError, RecursionError):
        return Outcome("error", error="invalid_json")


def delivery_json(outcome):
    """Deterministic host envelope; decoded text fields are verbatim.

    Transport escaping is not text modification. Consumers must keep text as
    data and not interpolate it into executable templates or XML delimiters.
    """
    blocks = []
    for block in outcome.blocks:
        ref = block.reference
        identity = ({"kind": "task", "version": ref.version}
                    if isinstance(ref, TaskRef) else
                    {"kind": "memory", "id": ref.id, "revision": ref.revision})
        blocks.append({"reference": identity, "text": block.text})
    return json.dumps({"outcome": outcome.kind, "blocks": blocks,
                       "error": outcome.error}, ensure_ascii=True,
                      separators=(",", ":"), sort_keys=True)


if __name__ == "__main__":
    demo = freeze_snapshot("cycle-1", "task-sha-1", "Complete the original task.\n",
                           "Still working.", [])
    request = json.dumps({"cycle": "cycle-1", "task_version": "task-sha-1",
                          "decision": "intervene",
                          "references": [{"kind": "task", "version": "task-sha-1"}]})
    print(delivery_json(parse_and_render(request, demo, active_cycle="cycle-1",
                                        active_task_version="task-sha-1")))
