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

if __name__=="__main__": unittest.main()
