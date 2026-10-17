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
                 timeout=180):
        if mode not in {'fake', 'profile'}:
            raise PoSBridgeError('explicit PoS transport mode required')
        argv = [sys.executable, '-B', '-u', str(Path(worker_script).resolve(strict=True)),
                '--vendor', str(Path(vendor).resolve(strict=True)),
                '--episode-module', str(Path(episode_module).resolve(strict=True)),
                '--archive', str(Path(archive)), '--mode', mode]
        if mode == 'fake':
            argv += ['--fake-replies', str(Path(fake_replies).resolve(strict=True))]
        else:
            argv += ['--profile-file', str(Path(profile_file).resolve(strict=True)),
                     '--profile-name', profile_name]
        archive_path = Path(archive)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        self._stderr = archive_path.with_suffix('.stderr.log').open('ab')
        try:
            self.process = subprocess.Popen(argv, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=self._stderr, text=True,
                encoding='utf-8', bufsize=1)
        except BaseException:
            self._stderr.close()
            raise
        self.timeout = float(timeout)
        self.replies = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        self.sent = 0
        self.closed = False

    @classmethod
    def from_environment(cls):
        required = ('GA_POS_WORKER_SCRIPT', 'GA_POS_VENDOR_ROOT',
                    'GA_POS_EPISODE_MODULE', 'GA_POS_ARCHIVE', 'GA_POS_TRANSPORT')
        if any(not os.environ.get(name) for name in required):
            raise PoSBridgeError('PoS worker identity or archive missing')
        mode = os.environ['GA_POS_TRANSPORT']
        if mode == 'profile' and os.environ.get('GA_POS_LIVE_AUTHORIZED') != '1':
            raise PoSBridgeError('PoS profile transport is not authorized')
        return cls(worker_script=os.environ['GA_POS_WORKER_SCRIPT'],
                   vendor=os.environ['GA_POS_VENDOR_ROOT'],
                   episode_module=os.environ['GA_POS_EPISODE_MODULE'],
                   archive=os.environ['GA_POS_ARCHIVE'], mode=mode,
                   fake_replies=os.environ.get('GA_POS_FAKE_REPLIES'),
                   profile_file=os.environ.get('GA_POS_PROFILE_FILE'),
                   profile_name=os.environ.get('GA_POS_PROFILE_NAME'),
                   timeout=float(os.environ.get('GA_POS_TIMEOUT', '180')))

    def _read(self):
        try:
            for line in self.process.stdout:
                self.replies.put(line)
        finally:
            self.replies.put(None)

    def exchange(self, kind, **fields):
        if self.closed or self.process.poll() is not None:
            raise PoSBridgeError('PoS worker is unavailable')
        command = {'kind': kind, **fields}
        self.sent += 1
        try:
            self.process.stdin.write(json.dumps(command, ensure_ascii=False) + '\n')
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            self.close()
            raise PoSBridgeError('PoS command acceptance unknown; never resend') from error
        try:
            raw = self.replies.get(timeout=self.timeout)
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
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.process.stdin:
            self.process.stdin.close()
        if self.process.stdout:
            self.process.stdout.close()
        self._stderr.close()
        self._reader.join(timeout=1)
