"""Neutral subprocess runner shared by Task Agent and Monitor Agent."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time


def _bounded(text: str, max_length: int, marker: str) -> str:
    if len(text) <= max_length + len(marker) * 2:
        return text
    half = max_length // 2
    return f"{text[:half]}{marker}{text[-half:]}"


def code_run(code, code_type="python", timeout=60, cwd=None, code_cwd=None,
             stop_signal=None, maxlen=10000, myprint=print):
    """Run Python or a platform shell with bounded output and cancellation."""
    cwd = cwd or tempfile.gettempdir()
    code_cwd = code_cwd or cwd
    preview = (code[:60].replace("\n", " ") + "...") if len(code) > 60 else code.strip()
    yield f"[Action] Running {code_type} in {os.path.basename(cwd)}: {preview}\n"
    temp_path = None
    if code_type in {"python", "py"}:
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".ai.py", delete=False, mode="w", encoding="utf-8", dir=code_cwd
        )
        temp_file.write(code)
        temp_path = temp_file.name
        temp_file.close()
        command = [sys.executable, "-X", "utf8", "-u", temp_path]
    elif code_type in {"powershell", "bash", "sh", "shell", "ps1", "pwsh"}:
        if os.name == "nt":
            shell = "pwsh" if shutil.which("pwsh") else "powershell"
            prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            command = [shell, "-NoProfile", "-NonInteractive", "-Command", prefix + code]
        else:
            command = ["bash", "-c", code]
    else:
        return {"status": "error", "msg": f"Unsupported code type: {code_type}"}

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
    output = []

    def stream_reader(process):
        try:
            for raw_line in iter(process.stdout.readline, b""):
                try:
                    line = raw_line.decode("utf-8")
                except UnicodeDecodeError:
                    line = raw_line.decode("gbk", errors="ignore")
                output.append(line)
                myprint(line, end="")
        except Exception:
            pass

    process = None
    try:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, cwd=cwd, startupinfo=startupinfo,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
        started = time.time()
        reader = threading.Thread(target=stream_reader, args=(process,), daemon=True)
        reader.start()
        while reader.is_alive():
            timed_out = time.time() - started > timeout
            if timed_out or stop_signal:
                process.kill()
                output.append("\n[Timeout] Process terminated" if timed_out else "\n[Stopped] Process cancelled")
                break
            time.sleep(0.1)
        reader.join(timeout=1)
        exit_code = process.poll()
        stdout = "".join(output)
        display = _bounded(stdout, 600, "\n\n[omitted long output]\n\n")
        display = re.sub(r"`{4,}", lambda match: match.group(0)[:3] + "\u200b" + match.group(0)[3:], display)
        yield f"[Status] Exit Code: {exit_code}\n[Stdout]\n{display}\n"
        return {
            "status": "success" if exit_code == 0 else "error",
            "stdout": _bounded(stdout, maxlen, "\n\n[omitted long output]\n\n"),
            "exit_code": exit_code,
        }
    except Exception as exc:
        if process is not None:
            try: process.kill()
            except Exception: pass
        return {"status": "error", "msg": str(exc)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
