"""Diagnostic-local mutable frozen replay filesystem and tool dispatcher."""
from __future__ import annotations
import hashlib, os, shutil, subprocess, tarfile, tempfile
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
            try: proposed=validator.parse_slot(text); kind=validator.validate_transition(self.slot,proposed,set(self.receipts))
            except Exception as exc:
                self.events.append({"event":"dcec_dependency_transition_rejected","operation":op,"error_type":type(exc).__name__}); raise
            old_id=self.slot.get("id"); self.slot=proposed; self.events.append({"event":"dcec_dependency_transition_accepted","operation":op,"kind":kind,"old_id":old_id,"new_id":proposed.get("id")})
        self.working=text; self.working_path.write_text(text,encoding="utf-8")

    def dispatch(self,name,args):
        if name not in TOOLS: return self._error(name,"unknown tool")
        try:
            if name=="file_read":
                path=args["path"]; content=self._path(path).read_text(encoding="utf-8",errors="replace"); offset=int(args.get("offset",0)); max_chars=int(args.get("max_chars",20000)); view=content[offset:offset+max_chars]; lines=view.splitlines(True); start=int(args.get("start",1)); count=int(args.get("count",200)); selected=lines[-count:] if args.get("tail") else lines[start-1:start-1+count]
                return self._receipt(name,{"status":"ok","path":path,"content":"".join(selected),"start":start,"total_lines":len(content.splitlines()),"truncated":offset+len(view)<len(content) or len(selected)<len(lines)})
            if name in {"file_write","file_patch"}:
                path=args["path"]; p=self._path(path); p.parent.mkdir(parents=True,exist_ok=True); old=p.read_text(encoding="utf-8") if p.exists() else ""
                if name=="file_write":
                    mode=args.get("mode","replace"); content=args.get("content",""); new=content if mode=="replace" else old+content if mode=="append" else content+old
                else:
                    mode="patch"; old_text=args.get("old_text",""); new_text=args.get("new_text","")
                    if not old_text or old.count(old_text)!=1: return self._error(name,"old_text must match exactly once",path=path)
                    new=old.replace(old_text,new_text,1)
                if path=="monitor/working.md":
                    try: self._commit_working(new,mode)
                    except Exception as exc: return self._error(name,str(exc),path=path)
                else: p.write_text(new,encoding="utf-8")
                return self._receipt(name,{"status":"ok","path":path,"sha256":hashlib.sha256(new.encode()).hexdigest()})
            if name=="code_run":
                cwd=self.fs/"workspace" if (self.fs/"workspace").exists() else self.fs; typ=args.get("type","python"); cmd=["bash","-lc",args.get("code","")] if typ=="bash" else ["python","-c",args.get("code","")]
                p=subprocess.run(cmd,cwd=str(cwd),capture_output=True,text=True,timeout=int(args.get("timeout",60)),env={**os.environ,"NO_PROXY":"*","no_proxy":"*"}); return self._receipt(name,{"status":"success" if p.returncode==0 else "error","exit_code":p.returncode,"stdout":p.stdout[-4000:],"stderr":p.stderr[-4000:]})
            if name=="wait": return {"status":"terminal","action":"defer"}
            if name=="intervene": return {"status":"terminal","action":"continue","message":args.get("message","")}
            return {"status":"terminal","action":"allow_complete"}
        except subprocess.TimeoutExpired: return self._receipt(name,{"status":"error","reason":"timeout"})
        except Exception as exc: return self._error(name,str(exc),exception_type=type(exc).__name__)

    def close(self): shutil.rmtree(self.temp_root,ignore_errors=True)
