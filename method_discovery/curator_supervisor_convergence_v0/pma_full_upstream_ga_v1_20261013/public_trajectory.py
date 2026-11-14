# Independent copy of GenericAgent-main/task_trajectory.py at 9eddf569.
"""Framework-independent, lossless public-event protocol (no model calls).

Adapters supply visible JSON values and stable event identities. Repeated
content is never deduplicated. Provider-private state belongs to its owner,
not to this public channel. Historical calls are data, never executable tools.
"""
from copy import deepcopy
import json

SCHEMA = "public-task-trajectory-v1"


def batch_rounds(value=4):
    if type(value) is not int or value < 1:
        raise ValueError("pma_batch_rounds must be a positive integer")
    return value


def json_copy(value):
    # Reject lossy repr/default=str fallbacks and non-JSON values.
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    decoded = json.loads(encoded)
    if decoded != value:
        raise ValueError("public event must be losslessly JSON representable")
    return deepcopy(decoded)


class PublicTrajectory:
    """One round's append-only events, with identity-only replay protection."""

    def __init__(self, round_number):
        if type(round_number) is not int or round_number < 1:
            raise ValueError("positive round number required")
        self.round_number = round_number
        self.events = []
        self._identities = {}

    def record(self, event_id, kind, payload):
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("stable source event identity required")
        if kind not in {"input", "request_attempt", "framework_input", "assistant", "assistant_partial", "tool_result", "tool_status", "round_status"}:
            raise ValueError("unknown public event kind")
        payload = json_copy(payload)
        identity = json.dumps([kind, payload], ensure_ascii=False,
                              allow_nan=False, sort_keys=True)
        if event_id in self._identities:
            if self._identities[event_id] != identity:
                raise ValueError("event identity reused for different data")
            return
        self._identities[event_id] = identity
        self.events.append({"event_id": event_id, "sequence": len(self.events) + 1,
                            "kind": kind, "payload": payload})

    def snapshot(self):
        return {"schema": SCHEMA, "round": self.round_number,
                "events": deepcopy(self.events)}


def validate_trajectory(value, *, round_number, status=None):
    if (not isinstance(value, dict) or set(value) != {"schema", "round", "events"}
            or value["schema"] != SCHEMA or type(value["round"]) is not int
            or value["round"] != round_number
            or not isinstance(value["events"], list)):
        raise ValueError("invalid public trajectory envelope")
    ledger = PublicTrajectory(round_number)
    calls, settled = set(), set()
    for index, event in enumerate(value["events"], 1):
        if (not isinstance(event, dict) or set(event) !=
                {"event_id", "sequence", "kind", "payload"}
                or type(event["sequence"]) is not int or event["sequence"] != index):
            raise ValueError("public event order is not contiguous")
        ledger.record(event["event_id"], event["kind"], event["payload"])
        payload = event["payload"]
        if not isinstance(payload, dict):
            raise ValueError("public event payload must be an object")
        if event["kind"] == "assistant":
            ids = payload.get("tool_call_ids", [])
            if (not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids)
                    or len(set(ids)) != len(ids) or calls.intersection(ids)):
                raise ValueError("invalid public tool-call identity")
            calls.update(ids)
        if event["kind"] in {"tool_result", "tool_status"}:
            call_id = payload.get("tool_call_id")
            if call_id not in calls or call_id in settled:
                raise ValueError("unpaired or duplicate public tool receipt")
            settled.add(call_id)
    if len(ledger.events) != len(value["events"]):
        raise ValueError("duplicate event in serialized round")
    if calls != settled:
        raise ValueError("public tool call lacks receipt or explicit outcome status")
    if status is not None:
        states = [e for e in ledger.events if e["kind"] == "round_status"]
        if (len(states) != 1 or states[0] != ledger.events[-1]
                or states[0]["payload"].get("status") != status):
            raise ValueError("round status is missing, reordered or inconsistent")
        if status in {"normal", "parse_error", "completed"}:
            kinds = [e["kind"] for e in ledger.events]
            if not kinds or kinds[0] != "input" or kinds.count("assistant") != 1:
                raise ValueError("accepted round lacks real input or assistant output")
    return ledger.snapshot()


def format_trajectory(value):
    """Serialize the full event envelope as inert evidence, without shortening."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
