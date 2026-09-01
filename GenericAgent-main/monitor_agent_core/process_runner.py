"""Private analysis subprocess runner for Monitor Agent."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time


def _bounded(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n[omitted long output]\n" + text[-half:]


def run_analysis(code: str, code_type: str, timeout: int, cwd: str,
                 stop_event: threading.Event | None = None, output_limit: int = 12000) -> dict:
    temp_path = None
    if code_type == "python":
        stream = tempfile.NamedTemporaryFile(
            suffix=".monitor.py", delete=False, mode="w", encoding="utf-8", dir=cwd
        )
        stream.write(code)
        temp_path = stream.name
        stream.close()
        command = [sys.executable, "-X", "utf8", "-u", temp_path]
    elif code_type == "powershell" and os.name == "nt":
        shell = "pwsh" if shutil.which("pwsh") else "powershell"
        prefix = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        command = [shell, "-NoProfile", "-NonInteractive", "-Command", prefix + code]
    elif code_type == "bash" and os.name != "nt":
        command = ["bash", "-c", code]
    else:
        return {"status": "error", "error": f"Unsupported analysis type: {code_type}"}

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
    output = []
    process = None
    try:
        process = subprocess.Popen(
            command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            bufsize=0, startupinfo=startupinfo,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )

        def read_output():
            for line in iter(process.stdout.readline, b""):
                try: output.append(line.decode("utf-8"))
                except UnicodeDecodeError: output.append(line.decode("gbk", errors="replace"))

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        started = time.monotonic()
        reason = None
        while reader.is_alive():
            if stop_event is not None and stop_event.is_set():
                reason = "cancelled"
            elif time.monotonic() - started > timeout:
                reason = "timeout"
            if reason:
                process.kill()
                break
            time.sleep(0.1)
        reader.join(timeout=1)
        exit_code = process.poll()
        stdout = "".join(output)
        if reason: stdout += f"\n[{reason}] process terminated"
        return {
            "status": "success" if exit_code == 0 else "error",
            "stdout": _bounded(stdout, output_limit),
            "exit_code": exit_code,
        }
    except Exception as exc:
        if process is not None:
            try: process.kill()
            except Exception: pass
        return {"status": "error", "error": str(exc)}
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
