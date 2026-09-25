"""D1 frozen replay runner.  Real execution is fail-closed behind an external authorization."""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
try:
    from .d1_harness import load_manifest, verify_sources, verify_snapshot_files, build_all, canon, sha
    from .snapshot_dispatcher import FrozenSnapshot
except ImportError:
    from d1_harness import load_manifest, verify_sources, verify_snapshot_files, build_all, canon, sha
    from snapshot_dispatcher import FrozenSnapshot

def bundle_files():
    return ["manifest.json","run_d1.py","snapshot_dispatcher.py","d1_harness.py","vendor/dcec_control_slot.py"]
def bundle_hash():
    rows=[]
    for rel in bundle_files():
        p=HERE/rel; rows.append({"path":rel,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    return hashlib.sha256(canon(rows)).hexdigest(), rows
def current_working_view(snap,limit=4000):
    text=snap.working
    if not snap.protocol: return "Current replay working state:\n"+text[:limit]
    first=text.splitlines(True)[0] if text.splitlines(True) else ""
    prose=text[len(first):] if first else text
    return "Current replay working state:\n"+first[:512]+prose[:max(0,limit-len(first)-29)]
def execute_records(manifest,output_root,provider_factory=None):
    output_root=Path(output_root)
    if output_root.exists(): raise SystemExit("D1 output already exists")
    output_root.mkdir(parents=True)
    sys.path.insert(0,str(ROOT/"GenericAgent-main"))
    from monitor_agent_core.configuration import load_profile
    from monitor_agent_core.provider import MonitorProviderClient
    cfg=load_profile(manifest["shared"]["supervisor_profile"], ROOT/"monitor_config/models.local.json")
    for record in build_all(manifest)["records"]:
        started=time.time(); case=dict(manifest["cases"][record["case_key"]]); case["protocol"]=record["condition"]=="PROTOCOL"; snap=FrozenSnapshot(case,ROOT)
        raw={"run_id":record["run_id"],"case":record["case_key"],"condition":record["condition"],"logical_calls":0,"requests":[],"tool_calls":[],"working_timeline":[],"events":[]}
        try:
            client=(provider_factory(cfg,record) if provider_factory else MonitorProviderClient(manifest["shared"]["supervisor_profile"],cfg)); client.restore_request_snapshot(record["request"]); tools=record["request"]["tools"]
            for logical in range(1,int(manifest["shared"]["logical_call_limit"])+1):
                snap.working=snap.working_path.read_text(encoding="utf-8"); view=current_working_view(snap)
                request_payload={"system":client.system,"messages":client.history+[{"role":"user","content":[{"type":"text","text":view}]}],"tools":tools,"model_parameters":record["request"].get("model_parameters")}
                request_hash=hashlib.sha256(canon(request_payload)).hexdigest()
                old_prepare=getattr(client,"prepare_active_context",None); client.prepare_active_context=lambda:view
                try: blocks,usage=client._request(tools)
                finally: client.prepare_active_context=old_prepare
                raw["logical_calls"]=logical; raw["requests"].append({"logical_call":logical,"request_sha256":request_hash,"request":request_payload,"working_sha256":hashlib.sha256(snap.working.encode()).hexdigest(),"blocks":blocks,"usage":usage})
                client.history.append({"role":"assistant","content":blocks}); calls=[b for b in blocks if b.get("type")=="tool_use"]
                if not calls: raw["terminal"]={"action":"defer","reason":"model_text_without_control"}; break
                results=[]; terminal=None
                for call in calls:
                    name=call.get("name"); args=call.get("input") or {}; before=snap.working
                    outcome=snap.dispatch(name,args); raw["tool_calls"].append({"logical_call":logical,"name":name,"input":args,"result":outcome,"working_before":before,"working_after":snap.working})
                    results.append({"tool_use_id":call.get("id",""),"content":json.dumps(outcome,ensure_ascii=False)})
                    if outcome.get("status")=="terminal": terminal=outcome
                raw["events"].extend(snap.events); snap.events.clear()
                if terminal is not None: raw["terminal"]=terminal; break
                client.history.append({"role":"user","content":[{"type":"tool_result","tool_use_id":r["tool_use_id"],"content":r["content"]} for r in results]})
            else: raw["terminal"]={"action":"diagnostic_incomplete_budget"}
            raw["usage_records"]=getattr(client,"usage_records",[]); raw["request_attempts"]=getattr(client,"request_attempts",[]); raw["final_history"]=getattr(client,"history",[])
        except Exception as exc: raw["error_type"]=type(exc).__name__; raw["error"]=str(exc)[:500]
        finally:
            raw["elapsed_seconds"]=time.time()-started; raw["final_working"]=snap.working; raw["snapshot_identity"]={"case":record["case_key"],"repeat":record["repeat"]}; snap.close(); (output_root/(record["run_id"]+".json")).write_text(json.dumps(raw,indent=2,ensure_ascii=False),encoding="utf-8")
    return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--execute",action="store_true"); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args(); m=load_manifest(); verify_sources(m); verify_snapshot_files(m)
    if not args.execute: print(json.dumps({"materialized_records":len(build_all(m)["records"]),"provider_requests":0,"execution_authorized":False})); return 0
    auth_path=HERE/"execution_authorization.json"
    if not auth_path.is_file(): raise SystemExit("D1 execution authorization artifact is absent; no provider request was sent")
    auth=json.loads(auth_path.read_text(encoding="utf-8")); bh,rows=bundle_hash(); manifest_sha=hashlib.sha256((HERE/"manifest.json").read_bytes()).hexdigest()
    required={"authorization":True,"manifest_sha256":manifest_sha,"bundle_sha256":bh,"run_order_sha256":hashlib.sha256(canon(m["run_order"])).hexdigest()}
    if any(auth.get(k)!=v for k,v in required.items()): raise SystemExit("D1 authorization identity mismatch; no provider request was sent")
    return execute_records(m,auth["output_root"])
if __name__=="__main__": main()
