"""Offline-only D1 provider-ready replay materializer and tests."""
from __future__ import annotations
import argparse, copy, hashlib, json, tarfile, unittest
from pathlib import Path
try:
    from . import protocol_validator as pv
except ImportError:
    import protocol_validator as pv
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
def verify_sources(m):
    out={}
    for ck,c in m["cases"].items():
        out[ck]={}
        for n,s in c["source_files"].items():
            b=source_bytes(s); actual=sha(b)
            if actual != s["sha256"]: raise AssertionError(f"{ck}.{n}: hash mismatch")
            out[ck][n]={"sha256":actual,"bytes":len(b)}
    return out
def load_json_source(s): return json.loads(source_bytes(s).decode("utf-8"))
def base_request(m,key): return load_json_source(m["cases"][key]["request"])
def protocol_suffix(): return ("\n\nD1 PROTOCOL: monitor/working.md first line is canonical DCEC-CONTROL/1 JSON with exactly "
    "v,id,status,op,from,receipts. Use op=create for inactive-to-active, retain, replace or discharge; "
    "statuses requested/running/interrupted/unavailable/completed; op=requested is invalid. Receipts are "
    "opaque deterministic tool receipts. This diagnostic does not enable a completion guard.\n")
def protocol_initial(messages):
    out=copy.deepcopy(messages)
    if out and out[0].get("role")=="user" and out[0].get("content"):
        content=out[0]["content"]
        if isinstance(content,str): out[0]["content"] = content + "\nInitial private working state (PROTOCOL):\n" + pv.canonical(pv.inactive())
        elif isinstance(content,list) and content and isinstance(content[0],dict) and content[0].get("type")=="text":
            content[0]["text"] += "\nInitial private working state (PROTOCOL):\n"+pv.canonical(pv.inactive())
    return out
def build_request(m,key,condition):
    req=base_request(m,key)
    if condition=="FREE": return req
    if condition!="PROTOCOL": raise ValueError(condition)
    req["system"] += protocol_suffix(); req["messages"]=protocol_initial(req["messages"]); return req
def treatment_diff(m,key):
    f,p=build_request(m,key,"FREE"),build_request(m,key,"PROTOCOL")
    return {"free_request_sha256":sha(canon(f)),"protocol_request_sha256":sha(canon(p)),
      "shared_fields_equal":{k:f.get(k)==p.get(k) for k in ("tools","root_handoff","model_parameters")},
      "allowed_differences":["system strict representation contract","initial inactive control slot"],"completion_guard":False}
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
    def test_protocol_validator(self):
        old=pv.inactive(); new={"v":1,"id":"D1","status":"requested","op":"create","from":None,"receipts":[]}
        self.assertEqual(pv.validate_transition(old,new),"create")
        with self.assertRaises(ValueError): pv.validate_transition(old,{**new,"op":"requested"})
        self.assertEqual(pv.validate_transition(new,{"v":1,"id":None,"status":"none","op":"discharge","from":"D1","receipts":["r1"]},["r1"]),"discharge")
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
        (a.materialize/"treatment_diffs.json").write_text(json.dumps({k:treatment_diff(m,k) for k in m["cases"]},indent=2),encoding="utf-8"); return 0
    ap.error("use --self-test or --materialize")
if __name__=="__main__": raise SystemExit(main())
