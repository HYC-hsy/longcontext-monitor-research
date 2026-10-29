"""Default-off GA-side IPC for an isolated released-core PoS worker."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone


class PoSBridgeError(RuntimeError):
    pass


class PoSBridge:
    def __init__(self, *, worker_script, vendor, episode_module, archive,
                 mode, fake_replies=None, profile_file=None, profile_name=None,
                 timeout=180, deadline_epoch=None, run_id=None, task_id=None,
                 binding_file=None):
        if mode not in {'fake', 'profile'}:
            raise PoSBridgeError('explicit PoS transport mode required')
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise PoSBridgeError('invalid PoS per-provider timeout')
        if mode == 'profile' and deadline_epoch is None:
            raise PoSBridgeError('PoS profile requires a fixed overall deadline')
        uncapped = deadline_epoch == 'uncapped'
        deadline_epoch = (None if uncapped else float(deadline_epoch) if deadline_epoch is not None
                          else time.time() + timeout)  # bounded fake-only fixture
        remaining = None if uncapped else deadline_epoch - time.time()
        if not uncapped and (not math.isfinite(deadline_epoch) or remaining <= 0):
            raise PoSBridgeError('PoS overall deadline invalid or expired before worker start')
        # Convert the frozen wall deadline once; polling never refreshes the budget.
        deadline_monotonic = None if uncapped else time.monotonic() + remaining
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
        self.timeout = timeout  # individual provider call, not IPC command budget
        self.deadline_epoch = deadline_epoch
        self.deadline_monotonic = deadline_monotonic
        self.replies = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.sent = 0
        self.closed = False
        self.close_status = None
        self.diagnostic_persist_error_type = None

    def _diagnose(self, **fields):
        """Best-effort bounded metadata only; never record prompts or raw errors."""
        row = {'time': datetime.now(timezone.utc).isoformat(),
               'run_id': self.run_id, 'task_id': self.task_id, **fields}
        try:
            with self.archive_path.with_suffix('.bridge.jsonl').open('ab') as stream:
                stream.write((json.dumps(row, ensure_ascii=True) + '\n').encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, TypeError, ValueError) as error:
            self.diagnostic_persist_error_type = type(error).__name__

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
        command_id = 'cmd-' + str(self.sent + 1).zfill(6)
        start = time.monotonic()
        sent = False
        send_started = False
        received = False
        self._diagnose(event='command_started', command_id=command_id,
                       command_type=kind, overall_deadline_epoch=self.deadline_epoch,
                       provider_timeout_seconds=self.timeout)
        try:
            if self.closed or self.process.poll() is not None:
                raise PoSBridgeError('PoS worker is unavailable')
            if self.deadline_monotonic is not None and self.deadline_monotonic - time.monotonic() <= 0:
                raise PoSBridgeError('PoS overall deadline expired before command send')
            command = {'kind': kind, **fields}
            self.sent += 1
            send_started = True
            try:
                self.process.stdin.write(json.dumps(command, ensure_ascii=True) + '\n')
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as error:
                raise PoSBridgeError('PoS command acceptance unknown; never resend') from error
            sent = True
            self._diagnose(event='command_sent', command_id=command_id,
                           command_type=kind, request_sent=True)
            while True:
                if self.closed:
                    raise PoSBridgeError('PoS command cancelled or bridge closed; never resend')
                remaining = (None if self.deadline_monotonic is None else
                             self.deadline_monotonic - time.monotonic())
                if remaining is not None and remaining <= 0:
                    raise PoSBridgeError('PoS overall deadline expired while awaiting command; never resend')
                try:
                    raw = self.replies.get(timeout=0.5 if remaining is None else min(0.5, remaining))
                    break
                except queue.Empty:
                    if self.process.poll() is not None and not self._reader.is_alive():
                        raise PoSBridgeError('PoS worker exited without receipt')
                    # Empty during a short poll is not a command failure.
            if raw is None:
                raise PoSBridgeError('PoS worker exited without receipt')
            received = True
            try:
                receipt = json.loads(raw)
            except (ValueError, TypeError) as error:
                raise PoSBridgeError('PoS receipt malformed; never resend') from error
            if not isinstance(receipt, dict):
                raise PoSBridgeError('PoS receipt malformed; never resend')
            if receipt.get('status') != 'ok' or not isinstance(receipt.get('result'), dict):
                raise PoSBridgeError('PoS worker failed: ' + str(receipt.get('error')))
            self._diagnose(event='command_finished', command_id=command_id,
                           command_type=kind, outcome='receipt_ok', request_sent=sent,
                           result_unknown=False, elapsed_seconds=time.monotonic()-start)
            return receipt['result']
        except BaseException as error:
            message = str(error) if isinstance(error, PoSBridgeError) else '[redacted]'
            if message.startswith('PoS worker failed:'):
                message = 'PoS worker failed; private receipt details redacted'
            frames = [{'file': Path(frame.filename).name, 'function': frame.name,
                       'line': frame.lineno} for frame in traceback.extract_tb(error.__traceback__)]
            self._diagnose(event='command_finished', command_id=command_id,
                           command_type=kind, outcome='exception', request_sent=sent,
                           result_unknown=send_started and not received,
                           exception_type=type(error).__name__, message=message,
                           stack=frames, elapsed_seconds=time.monotonic()-start)
            try:
                self.close()
            except BaseException as cleanup_error:
                self._diagnose(event='cleanup_failed', command_id=command_id,
                               command_type=kind,
                               exception_type=type(cleanup_error).__name__)
            raise

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
        self._diagnose(event='bridge_closed', close_status=self.close_status,
                       worker_return_code=self.process.returncode,
                       commands_sent=self.sent)
        try:
            with target.open('xb') as stream:
                stream.write((json.dumps({'status': self.close_status,
                    'worker_return_code': self.process.returncode,
                    'commands_sent': self.sent, 'run_id': self.run_id,
                    'task_id': self.task_id,
                    'diagnostic_persist_error_type':
                        self.diagnostic_persist_error_type}) + '\n').encode('utf-8'))
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            self.close_persist_error = type(error).__name__ + ': ' + str(error)
