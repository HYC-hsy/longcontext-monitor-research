"""Start original local Unix transport, then capture actual frozen worker."""
import socket
import subprocess
import sys
import time
from pathlib import Path

python = sys.executable
with Path('/logs/local_transport.log').open('w') as log:
    process = subprocess.Popen([python, '/opt/genericagent-source/isolated_transport.py', 'local'], stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 30
        while True:
            try:
                with socket.create_connection(('127.0.0.1', 18765), timeout=1): break
            except OSError:
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('local transport did not start')
                time.sleep(0.05)
        subprocess.run([python, '/checks/capture_worker.py', '--bundle', '/logs', '--output', '/logs/capture.json',
            '--source', '/opt/genericagent-source', '--profile', '/pilot-config/models.json',
            '--workspace', '/app', '--unix-transport'], check=True)
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
