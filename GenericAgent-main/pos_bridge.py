"""Default-off GA-side IPC for an isolated released-core PoS worker."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time


class PoSBridgeError(RuntimeError):
    pass


class PoSBridge:
    def __init__(self, *, worker_script, vendor, episode_module, archive,
                 mode, fake_replies=None, profile_file=None, profile_name=None,
                 timeout=180, deadline_epoch=None, run_id=None, task_id=None,
                 binding_file=None):
        if mode not in {'fake', 'profile'}:
            raise PoSBridgeError('explicit PoS transport mode required')
        argv = [sys.executable, '-B', '-u', str(Path(worker_script).resolve(strict=True)),
                '--vendor', str(Path(vendor).resolve(strict=True)),
                '--episode-module', str(Path(episode_module).resolve(strict=True)),
                '--archive', str(Path(archive)), '--mode', mode]
        if run_id: argv += ['--run-id', run_id]
        if task_id: argv += ['--task-id', task_id]
        if mode == 'fake':
            argv += ['--fake-replies', str(Path(fake_replies).resolve(strict=True))]
        else:
            if not binding_file:
                raise PoSBridgeError('PoS profile requires frozen run binding')
            binding_path = Path(binding_file).resolve(strict=True)
            bound = json.loads(binding_path.read_text(encoding='utf-8'))
            if (bound.get('schema') != 'pos-ga-transport-binding-v1' or
                    bound.get('transport') != 'profile' or
                    bound.get('run_id') != run_id or bound.get('task_id') != task_id or
                    binding_path.parent != Path(archive).resolve(strict=False).parent):
                raise PoSBridgeError('PoS profile binding identity differs')
            argv += ['--profile-file', str(Path(profile_file).resolve(strict=True)),
                     '--profile-name', profile_name,
                     '--binding-file', str(binding_path)]
        archive_path = Path(archive)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_path = archive_path
        self.run_id, self.task_id = run_id, task_id
        self._stderr = archive_path.with_suffix('.stderr.log').open('ab')
        try:
            self.process = subprocess.Popen(argv, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self._stderr, text=True,
                encoding='utf-8', bufsize=1)
        except BaseException:
            self._stderr.close()
            raise
        self.timeout = float(timeout)
        self.deadline_epoch = float(deadline_epoch) if deadline_epoch else None
        self.replies = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.sent = 0
        self.closed = False
        self.close_status = None

    def record_host(self, kind, payload):
        """Append original GA fact before auxiliary PoS processing."""
        row = {'kind': kind, 'payload': payload, 'worker_sent_commands': self.sent}
        with self.archive_path.with_suffix('.host.jsonl').open('ab') as stream:
            stream.write((json.dumps(row, ensure_ascii=True, default=str) + '\n').encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())

    @classmethod
    def from_environment(cls):
        required = ('GA_POS_WORKER_SCRIPT', 'GA_POS_VENDOR_ROOT',
                    'GA_POS_EPISODE_MODULE', 'GA_POS_ARCHIVE', 'GA_POS_TRANSPORT')
        if any(not os.environ.get(name) for name in required):
            raise PoSBridgeError('PoS worker identity or archive missing')
        mode = os.environ['GA_POS_TRANSPORT']
        return cls(worker_script=os.environ['GA_POS_WORKER_SCRIPT'],
                   vendor=os.environ['GA_POS_VENDOR_ROOT'],
                   episode_module=os.environ['GA_POS_EPISODE_MODULE'],
                   archive=os.environ['GA_POS_ARCHIVE'], mode=mode,
                   fake_replies=os.environ.get('GA_POS_FAKE_REPLIES'),
                   profile_file=os.environ.get('GA_POS_PROFILE_FILE'),
                   profile_name=os.environ.get('GA_POS_PROFILE_NAME'),
                   timeout=float(os.environ.get('GA_POS_TIMEOUT', '180')),
                   deadline_epoch=os.environ.get('GA_POS_DEADLINE_EPOCH'),
                   run_id=os.environ.get('GA_BENCH_RUN_ID'),
                   task_id=os.environ.get('GA_BENCH_TASK_ID'),
                   binding_file=os.environ.get('GA_POS_BINDING_FILE'))

    def _read(self):
        try:
            for line in self.process.stdout:
                self.replies.put(line)
        finally:
            self.replies.put(None)

    def exchange(self, kind, **fields):
        if self.closed or self.process.poll() is not None:
            raise PoSBridgeError('PoS worker is unavailable')
        remaining = (self.deadline_epoch - time.time()
                     if self.deadline_epoch is not None else self.timeout)
        if remaining <= 0:
            raise PoSBridgeError('PoS overall deadline expired before command send')
        command = {'kind': kind, **fields}
        self.sent += 1
        try:
            self.process.stdin.write(json.dumps(command, ensure_ascii=True) + '\n')
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            self.close()
            raise PoSBridgeError('PoS command acceptance unknown; never resend') from error
        try:
            raw = self.replies.get(timeout=min(self.timeout, remaining))
        except queue.Empty as error:
            self.close()
            raise PoSBridgeError('PoS command result unknown; never resend') from error
        if raw is None:
            self.close()
            raise PoSBridgeError('PoS worker exited without receipt')
        try:
            receipt = json.loads(raw)
        except (ValueError, TypeError) as error:
            self.close()
            raise PoSBridgeError('PoS receipt malformed; never resend') from error
        if receipt.get('status') != 'ok' or not isinstance(receipt.get('result'), dict):
            self.close()
            raise PoSBridgeError('PoS worker failed: ' + str(receipt.get('error')))
        return receipt['result']

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.process.stdin:
            try: self.process.stdin.close()
            except OSError: pass
        if self.process.poll() is None:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                    self.close_status = 'forced_terminate_after_grace_timeout'
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
                    self.close_status = 'forced_kill_after_terminate_timeout'
        if self.close_status is None:
            self.close_status = 'graceful_exit' if self.process.returncode == 0 else 'worker_error_exit'
        if self.process.stdout:
            self.process.stdout.close()
        self._stderr.close()
        self._reader.join(timeout=1)
        target = self.archive_path.with_suffix('.close.json')
        try:
            with target.open('xb') as stream:
                stream.write((json.dumps({'status': self.close_status,
                    'worker_return_code': self.process.returncode,
                    'commands_sent': self.sent, 'run_id': self.run_id,
                    'task_id': self.task_id}) + '\n').encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            self.close_persist_error = type(error).__name__ + ': ' + str(error)
