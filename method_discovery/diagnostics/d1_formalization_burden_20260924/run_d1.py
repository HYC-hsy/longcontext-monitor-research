"""Future D1 entry point; fail-closed until a separate authorization artifact exists."""
import argparse, hashlib, json, os, sys, time
from pathlib import Path
try:
    from .d1_harness import load_manifest, verify_sources, build_all
except ImportError:
    from d1_harness import load_manifest, verify_sources, build_all

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--execute",action="store_true"); ap.add_argument("--dry-run",action="store_true"); args=ap.parse_args()
    m=load_manifest(); verify_sources(m)
    from d1_harness import verify_snapshot_files
    verify_snapshot_files(m)
    if args.execute and not m.get("execution_authorized",False):
        raise SystemExit("D1 execution is unauthorized; no provider request was sent")
    if args.execute:
        auth_path=Path(__file__).resolve().parent/"execution_authorization.json"
        if not auth_path.is_file(): raise SystemExit("D1 execution authorization artifact is absent")
        auth=json.loads(auth_path.read_text(encoding="utf-8"))
        manifest_bytes=(Path(__file__).resolve().parent/"manifest.json").read_bytes()
        if auth.get("authorization") is not True or auth.get("preparation_commit") != auth.get("expected_preparation_commit") or auth.get("manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest():
            raise SystemExit("D1 authorization identity mismatch; no provider request was sent")
        return execute_records(m, Path(auth.get("output_root", "method_discovery/diagnostics/d1_formalization_burden_20260924/formal_output")))
    print(json.dumps({"records":len(build_all(m)["records"]),"provider_requests_sent":0,"execution_authorized":False}))
def execute_records(manifest, output_root):
    """Execute exactly the frozen records after authorization; never retry records."""
    if output_root.exists(): raise SystemExit("D1 output already exists")
    output_root.mkdir(parents=True)
    sys.path.insert(0, str(ROOT / "GenericAgent-main"))
    from monitor_agent_core.configuration import load_profile
    from monitor_agent_core.provider import MonitorProviderClient
    try:
        from .snapshot_dispatcher import FrozenSnapshot
    except ImportError:
        from snapshot_dispatcher import FrozenSnapshot
    cfg=load_profile(manifest["shared"]["supervisor_profile"], ROOT / "monitor_config/models.local.json")
    cfg["max_retries"]=int(cfg.get("max_retries",2))
    for record in build_all(manifest)["records"]:
        started=time.time(); case=manifest["cases"][record["case_key"]]; condition=record["condition"]
        spec=dict(case); spec["protocol"]=condition=="PROTOCOL"; snap=FrozenSnapshot(spec,ROOT)
        raw={"run_id":record["run_id"],"condition":condition,"case":record["case_key"],"logical_calls":0,"requests":[]}
        try:
            client=MonitorProviderClient(manifest["shared"]["supervisor_profile"],cfg)
            request=record["request"]; client.restore_request_snapshot(request); tools=request["tools"]
            for logical in range(1,manifest["shared"]["logical_call_limit"]+1):
                blocks,usage=client._request(tools); raw["logical_calls"]=logical; raw["requests"].append({"logical_call":logical,"blocks":blocks,"usage":usage})
                client.history.append({"role":"assistant","content":blocks})
                calls=[b for b in blocks if b.get("type")=="tool_use"]
                if not calls: raw["terminal"]={"action":"defer","reason":"model_text_without_control"}; break
                results=[]; terminal=None
                for call in calls:
                    name=call.get("name"); args=call.get("input") or {}
                    outcome=snap.dispatch(name,args); results.append({"tool_use_id":call.get("id",""),"content":json.dumps(outcome,ensure_ascii=False)})
                    if outcome.get("status")=="terminal": terminal=outcome
                if terminal is not None: raw["terminal"]=terminal; break
                client.history.append({"role":"user","content":[{"type":"tool_result","tool_use_id":r["tool_use_id"],"content":r["content"]} for r in results]})
            else: raw["terminal"]={"action":"diagnostic_incomplete_budget"}
            raw["usage_records"]=client.usage_records; raw["request_attempts"]=client.request_attempts; raw["events"]=snap.events
        except Exception as exc:
            raw["error_type"]=type(exc).__name__; raw["error"]=str(exc)[:400]
        finally:
            raw["elapsed_seconds"]=time.time()-started; snap.close(); (output_root/(record["run_id"]+".json")).write_text(json.dumps(raw,indent=2,ensure_ascii=False),encoding="utf-8")
    return 0

if __name__=="__main__": main()
