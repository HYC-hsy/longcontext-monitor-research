"""Diagnostic-local mutable frozen replay filesystem and tool dispatcher."""
from __future__ import annotations
import hashlib, os, shutil, subprocess, sys, tarfile, tempfile, threading
from pathlib import Path
try:
    from .vendor import dcec_control_slot as validator
except ImportError:
    from vendor import dcec_control_slot as validator

TOOLS={"file_read","file_write","file_patch","code_run","wait","intervene","allow_complete"}

class FrozenSnapshot:
    def __init__(self,spec,root):
        self.spec=spec; self.root=Path(root); self.protocol=bool(spec.get("protocol")); self.temp_root=Path(tempfile.mkdtemp(prefix="d1-snapshot-")); self.events=[]; self.receipts={}; self._next_receipt=1; self.slot=validator.inactive_slot()
        self._materialize(); self.working_path=self._path("monitor/working.md")
        self.working_path.parent.mkdir(parents=True,exist_ok=True)
        if not self.working_path.exists(): self.working_path.write_text("",encoding="utf-8")
        self.working=self.working_path.read_text(encoding="utf-8")
        lines=self.working.splitlines(True)
        if lines and lines[0].startswith("DCEC-CONTROL/1"):
            self.working="".join(lines[1:])
        if self.protocol:
            self.working=validator.canonical_slot(validator.inactive_slot())+"\n"+self.working
            self.working_path.write_text(self.working,encoding="utf-8")
        self.workspace_path=self._path("task/workspace")
        if not self.workspace_path.is_dir(): raise FileNotFoundError("frozen task/workspace is absent")
        mapped=str(self.workspace_path).replace("\\","/")
        self.path_mapping={"/testbed":mapped,"/app":mapped}
        sys.path.insert(0,str(self.root/"GenericAgent-main"))
        from monitor_agent_core.workspace import MonitorWorkspace
        from monitor_agent_core.process_runner import AnalysisSessions
        self.monitor_workspace=MonitorWorkspace(self._path("task"),self._path("monitor"),task_mounts={"workspace":self.workspace_path})
        self.analysis=AnalysisSessions(self.workspace_path,threading.Event())

    def _materialize(self):
        if self.spec.get("checkpoint_tar"):
            with tarfile.open(self.root/self.spec["checkpoint_tar"]["path"]) as t: t.extractall(self.temp_root)
            self.fs=self.temp_root/"checkpoint-0001"
        else:
            self.fs=self.temp_root/"checkpoint-0001"; shutil.copytree(self.root/self.spec["directory"],self.fs)
        (self.fs/"monitor").mkdir(parents=True,exist_ok=True)

    def _path(self,virtual):
        return self.fs/virtual.strip("/")

    def _receipt(self,tool,data):
        rid=f"r{self._next_receipt:06d}"; self._next_receipt+=1; out=dict(data,receipt_id=rid)
        self.receipts[rid]={k:out.get(k) for k in ("tool","status","path","sha256","truncated","session_id","exit_code","reason","output_path") if k in out}; self.receipts[rid]["tool"]=tool
        self.events.append({"event":"receipt","receipt_id":rid,"tool":tool,"status":out.get("status")}); return out

    def _error(self,tool,msg,**extra): return self._receipt(tool,{"status":"error","error_type":"tool_error","error":msg,**extra})

    def _commit_working(self,text,op):
        if self.protocol:
            try:
                text=validator.ensure_slot(text,self.slot)
                proposed=validator.parse_slot(text); kind=validator.validate_transition(self.slot,proposed,set(self.receipts))
            except Exception as exc:
                self.events.append({"event":"dcec_dependency_transition_rejected","operation":op,"error_type":type(exc).__name__}); raise
            old_id=self.slot.get("id"); self.slot=proposed; self.events.append({"event":"dcec_dependency_transition_accepted","operation":op,"kind":kind,"old_id":old_id,"new_id":proposed.get("id")})
        self.monitor_workspace._atomic_write(self.working_path,text)
        self.working=text

    def dispatch(self,name,args):
        if name not in TOOLS: return self._error(name,"unknown tool")
        try:
            if name=="file_read":
                read_args=dict(args); read_args["virtual_path"]=read_args.pop("path")
                out=self.monitor_workspace.read_text(**read_args); return self._receipt(name,{"status":"ok",**out})
            if name in {"file_write","file_patch"}:
                path=args["path"]; p=self._path(path); p.parent.mkdir(parents=True,exist_ok=True); old=p.read_text(encoding="utf-8") if p.exists() else ""
                if name=="file_write":
                    mode=args.get("mode","replace"); content=args.get("content","")
                    if self.protocol and path=="monitor/working.md" and mode=="prepend":
                        first,prose=validator.slot_and_prose(old)
                        new=first+"\n"+content+prose
                    else: new=content if mode=="replace" else old+content if mode=="append" else content+old
                else:
                    mode="patch"; old_text=args.get("old_text",""); new_text=args.get("new_text","")
                    if not old_text or old.count(old_text)!=1: return self._error(name,"old_text must match exactly once",path=path)
                    new=old.replace(old_text,new_text,1)
                if path=="monitor/working.md":
                    try: self._commit_working(new,mode)
                    except Exception as exc: return self._error(name,str(exc),path=path)
                else: self.monitor_workspace.write_text(path,new,mode="replace")
                return self._receipt(name,{"status":"ok","path":path,"sha256":hashlib.sha256(new.encode()).hexdigest()})
            if name=="code_run":
                if args.get("session_id"):
                    out=self.analysis.read(args["session_id"],wait_seconds=args.get("wait_seconds",1),cancel=args.get("cancel",False))
                else:
                    code=args.get("code","")
                    for old,new in self.path_mapping.items(): code=code.replace(old,new)
                    out=self.analysis.start(code,code_type=args.get("type","python"),timeout=args.get("timeout",60),wait_seconds=args.get("wait_seconds",1))
                return self._receipt(name,out)
            if name=="wait": return {"status":"terminal","action":"defer"}
            if name=="intervene": return {"status":"terminal","action":"continue","message":args.get("message","")}
            return {"status":"terminal","action":"allow_complete"}
        except subprocess.TimeoutExpired: return self._receipt(name,{"status":"error","reason":"timeout"})
        except Exception as exc: return self._error(name,str(exc),exception_type=type(exc).__name__)

    def close(self):
        if hasattr(self,"analysis"): self.analysis.close()
        shutil.rmtree(self.temp_root,ignore_errors=True)
