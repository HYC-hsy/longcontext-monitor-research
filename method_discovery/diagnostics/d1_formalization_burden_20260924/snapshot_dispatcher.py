"""Frozen-snapshot tool dispatcher used by D1 offline replay tests."""
from __future__ import annotations
import hashlib, json, subprocess, tarfile, tempfile
from pathlib import Path
try:
    from .vendor import dcec_control_slot as validator
except ImportError:
    from vendor import dcec_control_slot as validator

TOOLS={"file_read","file_write","file_patch","code_run","wait","intervene","allow_complete"}
class FrozenSnapshot:
    def __init__(self, spec, root):
        self.spec=spec; self.root=Path(root); self.tar=None
        if spec.get("checkpoint_tar"):
            self.tar=tarfile.open(self.root/spec["checkpoint_tar"]["path"])
        self.monitor=Path(tempfile.mkdtemp(prefix="d1-monitor-"))
        self.receipts={}; self.events=[]; self.slot=validator.inactive_slot()
        initial=self._read_virtual("monitor/working.md") if self._exists_virtual("monitor/working.md") else ""
        self.working=initial
    def _member(self, virtual):
        path=virtual.strip("/")
        if path.startswith("monitor/"): return "checkpoint-0001/monitor/state/"+path[len("monitor/"):]
        return "checkpoint-0001/"+path
    def _exists_virtual(self, virtual):
        if self.tar:
            try: self.tar.getmember(self._member(virtual)); return True
            except KeyError: return False
        return (self.root/self.spec.get("directory","")/virtual).is_file()
    def _read_virtual(self, virtual):
        if self.tar:
            f=self.tar.extractfile(self._member(virtual))
            if f is None: raise FileNotFoundError(virtual)
            return f.read().decode("utf-8",errors="replace")
        return (self.root/self.spec.get("directory","")/virtual).read_text(encoding="utf-8")
    def _receipt(self, tool, data):
        rid="r"+hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:12]
        self.receipts[rid]={"tool":tool,"status":data.get("status","ok"),"sha256":hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()}
        data=dict(data); data["receipt_id"]=rid; self.events.append({"event":"receipt","receipt_id":rid,"tool":tool}); return data
    def _commit_working(self,text):
        if self.protocol:
            proposed=validator.parse_slot(text); kind=validator.validate_transition(self.slot,proposed,set(self.receipts)); self.slot=proposed
            self.events.append({"event":"slot_transition_accepted","kind":kind})
        self.working=text; (self.monitor/"working.md").write_text(text,encoding="utf-8")
    def dispatch(self,name,args):
        if name not in TOOLS: raise ValueError("unknown tool")
        if name=="file_read":
            content=self._read_virtual(args["path"]); lines=content.splitlines(True); start=int(args.get("start",1)); count=int(args.get("count",200)); selected=lines[-count:] if args.get("tail") else lines[start-1:start-1+count]; out={"status":"ok","path":args["path"],"content":"".join(selected),"start":start,"total_lines":len(lines),"truncated":len(selected)<len(lines)}; return self._receipt(name,out)
        if name in {"file_write","file_patch"}:
            path=args["path"]
            if path!="monitor/working.md": raise ValueError("only monitor/working.md is writable in replay")
            old=self.working
            if name=="file_write":
                mode=args.get("mode","replace"); text=args.get("content",""); new=text if mode=="replace" else old+text if mode=="append" else text+old
            else:
                old_text=args["old_text"]; new_text=args["new_text"]
                if not old_text or old.count(old_text)!=1: raise ValueError("old_text must match exactly once")
                new=old.replace(old_text,new_text,1)
            self._commit_working(new); return self._receipt(name,{"status":"ok","path":path,"sha256":hashlib.sha256(new.encode()).hexdigest()})
        if name=="code_run":
            proc=subprocess.run(["python","-c",args.get("code","pass")],cwd=str(self.monitor),capture_output=True,text=True,timeout=args.get("timeout",60)); return self._receipt(name,{"status":"success" if proc.returncode==0 else "error","exit_code":proc.returncode,"stdout":proc.stdout[-4000:]})
        if name=="intervene": return {"status":"terminal","action":"continue","message":args.get("message","")}
        if name=="wait": return {"status":"terminal","action":"defer"}
        return {"status":"terminal","action":"allow_complete"}
    def close(self):
        if self.tar: self.tar.close()
