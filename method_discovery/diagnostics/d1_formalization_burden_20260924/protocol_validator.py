"""Diagnostic-local copy of frozen DCEC-CONTROL/1 syntax/lifecycle rules."""
import json, re
PREFIX = "DCEC-CONTROL/1 "
MAX_RECEIPTS = 4
ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,96}$")
def inactive(): return {"v":1,"id":None,"status":"none","op":"none","from":None,"receipts":[]}
def canonical(slot): return PREFIX + json.dumps(slot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
def validate_shape(slot):
    if set(slot) != {"v","id","status","op","from","receipts"} or slot["v"] != 1: raise ValueError("exact fields")
    if slot["status"] not in {"none","requested","running","interrupted","unavailable","completed"}: raise ValueError("invalid status")
    if slot["op"] not in {"none","create","retain","replace","discharge"}: raise ValueError("invalid operation")
    if not isinstance(slot["receipts"],list) or len(slot["receipts"]) > MAX_RECEIPTS: raise ValueError("receipt bound")
    if any(not isinstance(x,str) or not ID_RE.fullmatch(x) for x in slot["receipts"]): raise ValueError("invalid receipt")
    if slot["status"] == "none":
        if slot["id"] is not None: raise ValueError("inactive id")
        if slot["op"] != "discharge" and (slot["from"] is not None or slot["receipts"]): raise ValueError("inactive refs")
    elif not isinstance(slot["id"],str) or not ID_RE.fullmatch(slot["id"]): raise ValueError("active id")
    if slot["from"] is not None and (not isinstance(slot["from"],str) or not ID_RE.fullmatch(slot["from"])): raise ValueError("from")
def validate_transition(old,new,known_receipts=()):
    validate_shape(new)
    if any(r not in set(known_receipts) for r in new["receipts"]): raise ValueError("unknown receipt")
    if old == new: return "unchanged"
    if old["id"] is None:
        if new["id"] is None and new["op"] == "none": return "prose_only"
        if new["id"] is None or new["op"] != "create" or new["from"] is not None: raise ValueError("inactive requires create")
        return "create"
    if new["id"] is None:
        if new["op"] != "discharge" or new["from"] != old["id"]: raise ValueError("active clear requires discharge")
        return "discharge"
    if new["op"] == "retain" and new["id"] == old["id"] and new["from"] in (None,old["id"]): return "retain"
    if new["op"] == "replace" and new["from"] == old["id"] and new["id"] != old["id"]: return "replace"
    raise ValueError("invalid lifecycle")
