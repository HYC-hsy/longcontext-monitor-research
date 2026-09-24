"""Model-free D1 replay plumbing.

The dispatcher exercises the treatment boundary only; it never invokes a
provider. A future runner may replace the model loop after separate
authorization, but this module intentionally fails closed.
"""
from __future__ import annotations
import copy, json
from pathlib import Path
try:
    from .vendor import dcec_control_slot as validator
except ImportError:
    from vendor import dcec_control_slot as validator

TOOLS = {"file_read","file_write","file_patch","code_run","wait","intervene","allow_complete"}

class DryRunDispatcher:
    def __init__(self, protocol: bool):
        self.protocol=protocol; self.working=""; self.slot=validator.inactive_slot(); self.receipts=set(); self.events=[]
    def write_working(self, text: str):
        if self.protocol:
            proposed=validator.parse_slot(text)
            kind=validator.validate_transition(self.slot, proposed, self.receipts)
            self.slot=proposed; self.events.append({"event":"accepted","kind":kind})
        self.working=text
    def dispatch(self, name, payload):
        if name not in TOOLS: raise ValueError("unknown tool")
        if name in {"file_write","file_patch"} and payload.get("path")=="monitor/working.md":
            self.write_working(payload.get("content", payload.get("new_text", "")))
        return {"status":"ok","tool":name}

def dry_run_protocol():
    p=DryRunDispatcher(True); inactive=validator.canonical_slot(validator.inactive_slot())
    created={"v":1,"id":"D1","status":"requested","op":"create","from":None,"receipts":[]}
    p.write_working(validator.canonical_slot(created)+"\nprose"); rejected=False
    try: p.write_working(validator.canonical_slot({**created,"op":"requested"})+"\nprose")
    except ValueError: rejected=True
    p.write_working(validator.canonical({"v":1,"id":"D1","status":"none","op":"discharge","from":"D1","receipts":[]})+"\nprose") if False else None
    return {"create_accepted":True,"historical_invalid_rejected":rejected,"state_unchanged_after_rejection":p.slot["id"]=="D1","completion_guard":False}

def main():
    raise SystemExit("D1 replay harness is preparation-only; authorization artifact required")
if __name__=="__main__": main()
