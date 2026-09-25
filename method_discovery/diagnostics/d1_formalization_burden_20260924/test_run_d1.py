"""0-provider execution-path tests for the D1 runner."""
import json, tempfile, unittest
from pathlib import Path
import run_d1, d1_harness
from vendor import dcec_control_slot as pv

class FakeClient:
    def __init__(self,cfg,record): self.history=[]; self.usage_records=[]; self.request_attempts=[]; self.system=""; self.n=0
    def restore_request_snapshot(self,request): self.system=request["system"]; self.history=list(request["messages"])
    def _request(self,tools):
        self.n+=1
        if self.n==1:
            return ([{"type":"tool_use","id":"t1","name":"file_write","input":{"path":"monitor/working.md","mode":"replace","content":pv.canonical_slot({"v":1,"id":"D1","status":"requested","op":"create","from":None,"receipts":[]})+"\nprose"}}],{})
        if self.n==2:
            bad=pv.canonical_slot({"v":1,"id":"D1","status":"requested","op":"requested","from":None,"receipts":[]})+"\nprose"
            return ([{"type":"tool_use","id":"t2","name":"file_write","input":{"path":"monitor/working.md","mode":"replace","content":bad}}],{})
        return ([{"type":"tool_use","id":"t3","name":"allow_complete","input":{}}],{})

class ExhaustClient(FakeClient):
    def _request(self,tools):
        self.n+=1
        return ([{"type":"tool_use","id":f"t{self.n}","name":"file_read","input":{"path":"task/original_task.txt"}}],{})

class TextThenToolClient(FakeClient):
    def _request(self,tools):
        self.n+=1
        if self.n==1: return ([{"type":"text","text":"I should inspect the evidence."}],{})
        if self.n==2: return ([{"type":"tool_use","id":"evidence","name":"file_read","input":{"path":"task/original_task.txt"}}],{})
        return ([{"type":"tool_use","id":"approve","name":"allow_complete","input":{}}],{})

class RunnerTests(unittest.TestCase):
    def test_fake_full_loop_and_recoverable_protocol_error(self):
        m=run_d1.load_manifest()
        # one record is sufficient to exercise the exact execute_records path.
        old=m["run_order"]; m["run_order"]=["C-PROTOCOL-r1"]
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"out"
            run_d1.execute_records(m,out,provider_factory=lambda cfg,record: FakeClient(cfg,record))
            raw=json.loads(next(out.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(raw["logical_calls"],3)
            self.assertEqual(raw["terminal"]["action"],"allow_complete")
            self.assertTrue(any(x["result"].get("status")=="error" for x in raw["tool_calls"]))
            self.assertTrue(raw["final_working"].startswith("DCEC-CONTROL/1"))
            self.assertTrue(all(sum("Current replay working state:" in str(m) for m in req["request"]["messages"]) == 1 for req in raw["requests"]))
        m["run_order"]=old

    def test_frozen_workspace_mapping_sessions_and_prepend(self):
        m=run_d1.load_manifest(); spec=dict(m["cases"]["S"],protocol=True)
        from snapshot_dispatcher import FrozenSnapshot
        snap=FrozenSnapshot(spec,run_d1.ROOT)
        try:
            self.assertIn("Sphinx",snap.dispatch("file_read",{"path":"task/workspace/README.rst"})["content"])
            mapped=snap.dispatch("code_run",{"type":"python","code":"print(open('/testbed/README.rst').read(20))"})
            self.assertEqual(mapped["status"],"success")
            started=snap.dispatch("code_run",{"type":"python","code":"import time; print('session'); time.sleep(.1)","wait_seconds":0})
            self.assertIn(started["status"],["running","success"])
            if started.get("session_id"):
                self.assertIn(snap.dispatch("code_run",{"session_id":started["session_id"],"wait_seconds":1})["status"],["success","running"])
            slot=snap.working.split("\n",1)[0]
            out=snap.dispatch("file_write",{"path":"monitor/working.md","mode":"prepend","content":"PROSE\n"})
            self.assertEqual(out["status"],"ok"); self.assertTrue(snap.working.startswith(slot))
        finally: snap.close()

    def test_six_call_exhaustion_and_archive(self):
        m=run_d1.load_manifest(); old=m["run_order"]; m["run_order"]=["C-FREE-r1"]
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"out"; run_d1.execute_records(m,out,provider_factory=lambda cfg,record: ExhaustClient(cfg,record))
            raw=json.loads(next(out.glob("*.json")).read_text(encoding="utf-8")); self.assertEqual(raw["logical_calls"],6); self.assertEqual(raw["terminal"]["action"],"diagnostic_incomplete_budget"); self.assertEqual(len(raw["requests"]),6)
        m["run_order"]=old

    def test_no_tool_text_continues_to_evidence_and_control(self):
        m=run_d1.load_manifest(); m["run_order"]=["C-FREE-r1"]
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"out"
            run_d1.execute_records(m,out,provider_factory=lambda cfg,record: TextThenToolClient(cfg,record))
            raw=json.loads(next(out.glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(raw["logical_calls"],3)
            self.assertEqual(raw["terminal"]["action"],"allow_complete")
            self.assertEqual(raw["tool_calls"][0]["name"],"file_read")
            self.assertEqual(raw["tool_calls"][0]["result"]["status"],"ok")
            self.assertIn(run_d1.NO_TOOL_CONTINUATION,str(raw["requests"][1]["request"]["messages"]))

    def test_all_historical_path_mappings_and_record_local_tmp(self):
        from snapshot_dispatcher import FrozenSnapshot
        m=run_d1.load_manifest()
        families={
            "S":("/opt/m2-artifacts/monitor/task_evidence/original_task.txt", "/opt/m2-artifacts/monitor/monitor_private/working.md"),
            "F":("/logs/agent/monitor/task_evidence/original_task.txt", "/logs/agent/monitor/monitor_private/working.md"),
        }
        for key,(task_path,monitor_path) in families.items():
            snap=FrozenSnapshot(dict(m["cases"][key],protocol=False),run_d1.ROOT)
            try:
                task=snap.dispatch("code_run",{"type":"python","code":f"print(open('{task_path}').read(30))"})
                self.assertEqual(task["status"],"success",task)
                marker=f"{key}-record-local-state"
                self.assertEqual(snap.dispatch("file_write",{"path":"monitor/working.md","content":marker})["status"],"ok")
                monitor=snap.dispatch("code_run",{"type":"python","code":f"print(open('{monitor_path}').read())"})
                self.assertEqual(monitor["status"],"success",monitor)
                self.assertIn(marker,monitor["stdout"])
                workspace_alias="/testbed" if key=="S" else "/app"
                workspace=snap.dispatch("code_run",{"type":"python","code":f"import os; print(os.path.isdir('{workspace_alias}'))"})
                self.assertEqual(workspace["status"],"success",workspace)
                self.assertIn("True",workspace["stdout"])
            finally: snap.close()
        for key in ("S","F","C"):
            spec=dict(m["cases"][key],protocol=False)
            first=FrozenSnapshot(spec,run_d1.ROOT)
            try:
                write=first.dispatch("code_run",{"type":"python","code":"open('/tmp/d1_probe','w').write('first-record')"})
                self.assertEqual(write["status"],"success",write)
                self.assertTrue((first.tmp_path/"d1_probe").is_file())
            finally: first.close()
            second=FrozenSnapshot(spec,run_d1.ROOT)
            try:
                self.assertFalse((second.tmp_path/"d1_probe").exists())
                probe=second.dispatch("code_run",{"type":"python","code":"import os; print(os.path.exists('/tmp/d1_probe'))"})
                self.assertEqual(probe["status"],"success",probe)
                self.assertIn("False",probe["stdout"])
            finally: second.close()

if __name__=="__main__": unittest.main()
