"""0-provider execution-path tests for the D1 runner."""
import json, tempfile, unittest
from pathlib import Path
import run_d1, d1_harness

class FakeClient:
    def __init__(self,cfg,record): self.history=[]; self.usage_records=[]; self.request_attempts=[]; self.system=""; self.n=0
    def restore_request_snapshot(self,request): self.system=request["system"]; self.history=list(request["messages"])
    def _request(self,tools):
        self.n+=1
        if self.n==1:
            return ([{"type":"tool_use","id":"t1","name":"file_write","input":{"path":"monitor/working.md","mode":"replace","content":"DCEC-CONTROL/1 {\"v\":1,\"id\":\"D1\",\"status\":\"requested\",\"op\":\"create\",\"from\":null,\"receipts\":[]}\nprose"}}],{})
        if self.n==2:
            return ([{"type":"tool_use","id":"t2","name":"file_write","input":{"path":"monitor/working.md","mode":"replace","content":"DCEC-CONTROL/1 {\"v\":1,\"id\":\"D1\",\"status\":\"requested\",\"op\":\"requested\",\"from\":null,\"receipts\":[]}\nprose"}}],{})
        return ([{"type":"tool_use","id":"t3","name":"allow_complete","input":{}}],{})

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
        m["run_order"]=old

if __name__=="__main__": unittest.main()
