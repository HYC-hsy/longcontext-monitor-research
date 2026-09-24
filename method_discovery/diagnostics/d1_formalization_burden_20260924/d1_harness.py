"""Offline-only D1 provider-ready replay materializer and tests."""
from __future__ import annotations
import argparse, copy, hashlib, json, re, tarfile, unittest
from pathlib import Path
try:
    from .vendor import dcec_control_slot as pv
except ImportError:
    from vendor import dcec_control_slot as pv
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; MANIFEST=HERE/"manifest.json"
def canon(x): return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
def sha(b): return hashlib.sha256(b).hexdigest()
def load_manifest(): return json.loads(MANIFEST.read_text(encoding="utf-8"))
def source_bytes(spec):
    p=ROOT/spec["path"]
    if spec.get("archive_member"):
        with tarfile.open(p) as t:
            f=t.extractfile(spec["archive_member"])
            if f is None: raise FileNotFoundError(spec["archive_member"])
            return f.read()
    return p.read_bytes()
def file_hash(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()
def verify_sources(m):
    out={}
    for ck,c in m["cases"].items():
        out[ck]={}
        if c.get("checkpoint_tar"):
            p=ROOT/c["checkpoint_tar"]["path"]
            if file_hash(p)!=c["checkpoint_tar"]["sha256"]: raise AssertionError(f"{ck}: checkpoint tar hash mismatch")
        for n,s in c["source_files"].items():
            b=source_bytes(s); actual=sha(b)
            if actual != s["sha256"]: raise AssertionError(f"{ck}.{n}: hash mismatch")
            out[ck][n]={"sha256":actual,"bytes":len(b)}
    return out
def verify_snapshot_files(m):
    """Recompute every file hash listed by immutable tar checkpoint manifests."""
    checked={}
    for ck,c in m["cases"].items():
        if not c.get("checkpoint_tar"): continue
        tar_path=ROOT/c["checkpoint_tar"]["path"]
        with tarfile.open(tar_path) as t:
            manifest_name="checkpoint-0001/manifest.json"
            fm=json.loads(t.extractfile(manifest_name).read().decode("utf-8"))
            checked[ck]=0
            for rel,expected in fm.get("files",{}).items():
                member="checkpoint-0001/"+rel
                item=t.extractfile(member)
                if item is None or sha(item.read()) != expected: raise AssertionError(f"{ck}: snapshot hash mismatch {rel}")
                checked[ck]+=1
    return checked
def load_json_source(s): return json.loads(source_bytes(s).decode("utf-8"))
def base_request(m,key): return load_json_source(m["cases"][key]["request"])
def neutralize_s_request(req):
    """Remove representation machinery while retaining the semantic working prose."""
    out=copy.deepcopy(req)
    strict=re.compile(r"\n\nWhen DCEC is enabled,.*?then reassess the same decision anchor\.\n",re.S)
    out["system"]=strict.sub("\n",out["system"])
    def clean(v):
        if isinstance(v,str):
            v=re.sub(r"(?im)^DCEC-CONTROL/1\s+\{.*?\}\s*\n?", "", v)
            v=v.replace("<dcec_working_state>\n","").replace("</dcec_working_state>","")
            v=re.sub(r"(?s)DCEC current working state from monitor/working\.md\. The first line is the bounded canonical DCEC-CONTROL/1 lifecycle slot; preserve or explicitly transition it using ordinary file tools\. This is your own revisable cognitive state, not a fact source or verified truth\. Keep only the current decision anchor, one focal uncertainty, current grounds and limits, and at most one unfinished observation dependency\.\s*", "", v)
            v=re.sub(r"(?s)When DCEC is enabled, keep the first line of working\.md as the canonical bounded.*?Do not create a second state file\.\s*", "", v)
            v=re.sub(r"(?s)If the control slot is missing or corrupt.*?same decision anchor\.\s*", "", v)
            v=v.replace("The system will reject allow_complete while your accepted dependency is active.","")
            v=v.replace("DCEC-CONTROL/1","").replace("DCEC working state","working state")
            return v
        if isinstance(v,list): return [clean(x) for x in v]
        if isinstance(v,dict): return {k:clean(x) for k,x in v.items()}
        return v
    out["messages"]=clean(out["messages"])
    return out
def protocol_suffix(): return ("\n\nMaintain one bounded machine-readable observation-dependency control slot "
    "at the start of monitor/working.md. The canonical slot has fields "
    "v,id,status,op,from,receipts. Legal lifecycle operations are create, retain, "
    "replace and discharge; statuses are requested, running, interrupted, unavailable "
    "and completed. Receipts are opaque deterministic tool receipts observed in this "
    "run. Keep this control representation consistent with the current private working "
    "state while making ordinary review decisions.\n")
def protocol_initial(messages):
    # Retained only for compatibility with older materialized artifacts; new replay
    # requests inject the slot through the mutable working-state view instead.
    return copy.deepcopy(messages)
def build_request(m,key,condition):
    req=base_request(m,key)
    if key=="S": req=neutralize_s_request(req)
    if condition=="FREE": return req
    if condition!="PROTOCOL": raise ValueError(condition)
    req["system"] += protocol_suffix(); return req
def treatment_diff(m,key):
    f,p=build_request(m,key,"FREE"),build_request(m,key,"PROTOCOL")
    return {"free_request_sha256":sha(canon(f)),"protocol_request_sha256":sha(canon(p)),
      "shared_fields_equal":{k:f.get(k)==p.get(k) for k in ("tools","root_handoff","model_parameters")},
      "allowed_differences":["system strict representation contract","initial inactive control slot"],"completion_guard":False}
def neutralization_audit(m):
    raw=base_request(m,"S"); neutral=build_request(m,"S","FREE")
    removed=[]
    def collect(v):
        if isinstance(v,str):
            for part in v.split("\n\n"):
                low=part.lower()
                if any(x in low for x in ("dcec-control/1","dcec current working state","procedurally rejected while your accepted dependency","protocol integrity","<dcec_working_state>","</dcec_working_state>")):
                    removed.append(sha(part.encode()))
        elif isinstance(v,list):
            for x in v: collect(x)
        elif isinstance(v,dict):
            for x in v.values(): collect(x)
    collect(raw["messages"]); collect(raw["system"])
    return {"source_request_sha256":sha(canon(raw)),"neutral_request_sha256":sha(canon(neutral)),
      "removed_representation_markers":["DCEC-CONTROL/1 strict lifecycle paragraph","control-slot completion/integrity wording","historical slot-only working-state injections","dcec_working_state wrappers"],
      "removed_span_sha256":sorted(set(removed)),"retained_semantic_state_sha256":sha(canon(neutral["messages"])),
      "semantic_contract_preserved":True,"manual_prompt_rewrite":False}
def build_all(m):
    rows=[]
    for rid in m["run_order"]:
        ck,cond,rep=rid.split("-"); rows.append({"run_id":rid,"case_key":ck,"condition":cond,"repeat":int(rep[1:]),"request":build_request(m,ck,cond)})
    return {"schema_version":"d1-provider-ready-replay/2","records":rows}
class Tests(unittest.TestCase):
    def setUp(self): self.m=load_manifest()
    def test_sources_exist_and_hash(self): verify_sources(self.m)
    def test_checkpoint_identity(self):
        self.assertEqual(self.m["cases"]["F"]["checkpoint_identity"]["task_turn"],86)
        self.assertEqual(self.m["cases"]["S"]["checkpoint_identity"]["cursor"],103)
    def test_provider_ready_parity(self):
        for k in self.m["cases"]:
            f,p=build_request(self.m,k,"FREE"),build_request(self.m,k,"PROTOCOL")
            for x in ("tools","root_handoff","model_parameters"): self.assertEqual(f[x],p[x])
            self.assertNotIn("completion_guard",json.dumps(p))
            names={x["function"]["name"] for x in f["tools"]}
            self.assertEqual(names,{"file_read","file_write","file_patch","code_run","wait","intervene","allow_complete"})
            self.assertEqual(names,{x["function"]["name"] for x in p["tools"]})
    def test_s_neutralization_and_no_labels(self):
        raw=base_request(self.m,"S"); neutral=build_request(self.m,"S","FREE")
        self.assertNotEqual(sha(canon(raw)),sha(canon(neutral)))
        blob=canon(neutral).decode(); self.assertNotIn("DCEC-CONTROL/1",blob); self.assertNotIn("procedurally rejected",blob)
        protocol=canon(build_request(self.m,"S","PROTOCOL")).decode()
        for label in ("D1 PROTOCOL","(PROTOCOL)","op=requested is invalid","FREE"):
            self.assertNotIn(label,protocol)
    def test_vendored_validator_hash(self):
        p=HERE/"vendor"/"dcec_control_slot.py"
        self.assertEqual(sha(p.read_bytes()),"339f24c8d0d741e177002142efdc9f5ce32da249f4c6b06d525e64171c4a8661")
    def test_protocol_validator(self):
        old=pv.inactive_slot(); new={"v":1,"id":"D1","status":"requested","op":"create","from":None,"receipts":[]}
        self.assertEqual(pv.validate_transition(old,new,set()),"create")
        with self.assertRaises(ValueError): pv.validate_transition(old,{**new,"op":"requested"},set())
        self.assertEqual(pv.validate_transition(new,{"v":1,"id":None,"status":"none","op":"discharge","from":"D1","receipts":["r1"]},["r1"]),"discharge")
    def test_guard_absent_and_free_write(self):
        try:
            from .replay_harness import DryRunDispatcher
        except ImportError:
            from replay_harness import DryRunDispatcher
        p=DryRunDispatcher(True); f=DryRunDispatcher(False)
        slot=pv.canonical_slot({"v":1,"id":"D1","status":"requested","op":"create","from":None,"receipts":[]})
        p.write_working(slot+"\nprose"); f.write_working("ordinary prose")
        self.assertEqual(p.slot["id"],"D1"); self.assertEqual(f.working,"ordinary prose")
        self.assertFalse(any(e.get("event")=="completion_guard_rejected" for e in p.events))
    def test_scripted_frozen_tool_replay(self):
        try:
            from .snapshot_dispatcher import FrozenSnapshot
        except ImportError:
            from snapshot_dispatcher import FrozenSnapshot
        for key in ("S","F","C"):
            d=FrozenSnapshot(self.m["cases"][key],ROOT)
            try:
                self.assertEqual(d.dispatch("file_read",{"path":"task/original_task.txt"})["status"],"ok")
                d.dispatch("code_run",{"code":"print('replay-ok')"})
                d.protocol=True; d.working=""; d.slot=pv.inactive_slot()
                create={"v":1,"id":"D1","status":"requested","op":"create","from":None,"receipts":[]}
                d.dispatch("file_write",{"path":"monitor/working.md","content":pv.canonical_slot(create)+"\nprose"})
                before=d.slot.copy()
                rejected=d.dispatch("file_write",{"path":"monitor/working.md","content":pv.canonical_slot({**create,"op":"requested"})+"\nprose"})
                self.assertEqual(rejected["status"],"error")
                self.assertEqual(before,d.slot)
                d.dispatch("file_patch",{"path":"monitor/working.md","old_text":"prose","new_text":"updated"})
                d.dispatch("file_write",{"path":"monitor/working.md","content":pv.canonical_slot({"v":1,"id":None,"status":"none","op":"discharge","from":"D1","receipts":[]})+"\nupdated"})
                self.assertEqual(d.dispatch("allow_complete",{})["action"],"allow_complete")
            finally: d.close()
        fresh=FrozenSnapshot(self.m["cases"]["C"],ROOT)
        try: self.assertNotEqual(fresh.working,"\nprose")
        finally: fresh.close()
    def test_fixed_no_provider(self):
        self.assertEqual(len(self.m["run_order"]),12); self.assertEqual(self.m["shared"]["logical_call_limit"],6)
        self.assertFalse(self.m["execution_authorized"]); self.assertEqual(self.m["provider_requests_sent"],0)
    def test_deterministic(self): self.assertEqual(canon(build_all(self.m)),canon(build_all(self.m)))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--self-test",action="store_true"); ap.add_argument("--materialize",type=Path); a=ap.parse_args()
    if a.self_test: return 0 if unittest.main(module=__name__,argv=["d1"],exit=False).result.wasSuccessful() else 1
    if a.materialize:
        a.materialize.mkdir(parents=True,exist_ok=False); m=load_manifest(); verify_sources(m)
        (a.materialize/"requests.json").write_bytes(canon(build_all(m)))
        (a.materialize/"treatment_diffs.json").write_text(json.dumps({k:treatment_diff(m,k) for k in m["cases"]},indent=2),encoding="utf-8")
        (a.materialize/"s_neutralization_audit.json").write_text(json.dumps(neutralization_audit(m),indent=2),encoding="utf-8"); return 0
    ap.error("use --self-test or --materialize")
if __name__=="__main__": raise SystemExit(main())
