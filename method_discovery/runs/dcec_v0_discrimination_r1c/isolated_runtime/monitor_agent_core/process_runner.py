"""Task-local analysis sessions with incremental reads and full output files."""
from __future__ import annotations

import codecs
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


class AnalysisSessions:
    def __init__(self, cwd, stop_event):
        self.cwd = Path(cwd)
        self.stop_event = stop_event
        self.sessions = {}

    @staticmethod
    def _terminate(process):
        if os.name == 'nt':
            if process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=0x08000000, timeout=2)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def start(self, code, code_type='python', timeout=60, wait_seconds=1):
        if self.stop_event.is_set():
            raise RuntimeError('Monitor is stopping; no new analysis can be started')
        if not isinstance(code, str) or not code.strip():
            raise ValueError('code must be nonempty text')
        if type(timeout) not in (int, float) or not 0 < timeout <= 300:
            raise ValueError('timeout must be in (0, 300] seconds')
        self._validate_wait(wait_seconds)
        session_id = uuid.uuid4().hex
        directory = self.cwd / 'audit' / 'commands' / session_id
        directory.mkdir(parents=True)
        if code_type == 'python':
            script = directory / 'script.py'
            script.write_text(code, encoding='utf-8')
            command = [sys.executable, '-X', 'utf8', '-u', str(script)]
        elif code_type == 'powershell' and os.name == 'nt':
            script = directory / 'script.ps1'
            script.write_text('[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;\n' + code,
                              encoding='utf-8-sig')
            command = ['pwsh' if shutil.which('pwsh') else 'powershell',
                       '-NoProfile', '-NonInteractive', '-File', str(script)]
        elif code_type == 'bash' and os.name != 'nt':
            script = directory / 'script.sh'
            script.write_text(code, encoding='utf-8')
            command = ['bash', str(script)]
        else:
            raise ValueError(f'Unsupported analysis type: {code_type}')
        output_path = directory / 'output.log'
        with output_path.open('wb') as output:
            process = subprocess.Popen(
                command, cwd=self.cwd, stdout=output, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL, start_new_session=os.name != 'nt',
                creationflags=0x08000000 if os.name == 'nt' else 0,
            )
        entry = dict(process=process, output=output_path, cursor=0, done=threading.Event(),
                     cancel=threading.Event(), reason=None, started=time.monotonic(), timeout=timeout)
        self.sessions[session_id] = entry
        threading.Thread(target=self._watch, args=(entry,), daemon=True).start()
        return self.read(session_id, wait_seconds=wait_seconds)

    def _watch(self, entry):
        process = entry['process']
        try:
            while process.poll() is None:
                if self.stop_event.is_set() or entry['cancel'].is_set():
                    entry['reason'] = 'cancelled'
                    break
                if time.monotonic() - entry['started'] >= entry['timeout']:
                    entry['reason'] = 'timeout'
                    break
                time.sleep(0.02)
            # Stop children left behind by a finished UNIX shell as well.
            if entry['reason'] or os.name != 'nt':
                self._terminate(process)
            process.wait(timeout=2)
        except Exception as exc:
            entry['reason'] = f'cleanup_error: {exc}'
            try:
                process.kill()
            except OSError:
                pass
        finally:
            metadata = {'exit_code': process.poll(), 'reason': entry['reason'],
                        'duration_seconds': time.monotonic() - entry['started']}
            try:
                entry['output'].with_name('result.json').write_text(json.dumps(metadata), encoding='utf-8')
            finally:
                entry['done'].set()

    @staticmethod
    def _validate_wait(value):
        if type(value) not in (int, float) or not 0 <= value <= 5:
            raise ValueError('wait_seconds must be between 0 and 5')

    def read(self, session_id, wait_seconds=1, cancel=False):
        self._validate_wait(wait_seconds)
        if type(cancel) is not bool:
            raise ValueError('cancel must be boolean')
        if session_id not in self.sessions:
            raise ValueError('Unknown session in this monitor process; archived output remains readable')
        entry = self.sessions[session_id]
        if cancel:
            entry['cancel'].set()
        entry['done'].wait(wait_seconds)
        finished = entry['done'].is_set()
        with entry['output'].open('rb') as stream:
            stream.seek(entry['cursor'])
            raw = stream.read(12000)
        end = entry['cursor'] + len(raw) >= entry['output'].stat().st_size
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        text = decoder.decode(raw, final=finished and end)
        buffered, _ = decoder.getstate()
        entry['cursor'] += len(raw) - len(buffered)
        unread = max(0, entry['output'].stat().st_size - entry['cursor'])
        exit_code = entry['process'].poll() if finished else None
        return {
            'status': ('success' if exit_code == 0 and not entry['reason'] else 'error') if finished else 'running',
            'session_id': session_id, 'stdout': text, 'exit_code': exit_code,
            'reason': entry['reason'], 'unread_bytes': unread,
            'output_path': 'monitor/' + entry['output'].relative_to(self.cwd).as_posix(),
            'next_read': {'session_id': session_id} if not finished or unread else None,
            'note': 'stdout is only the next output chunk, not the full result. Full output is archived. '
                    'This analysis session does not pause or resume the Task Agent.',
        }

    def close(self):
        for entry in self.sessions.values():
            entry['cancel'].set()
        deadline = time.monotonic() + 2.5
        for entry in self.sessions.values():
            entry['done'].wait(max(0, deadline - time.monotonic()))
