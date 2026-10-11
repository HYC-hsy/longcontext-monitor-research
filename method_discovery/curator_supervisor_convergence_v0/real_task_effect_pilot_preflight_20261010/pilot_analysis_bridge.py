"""Pilot-only trusted-host port for one fixed Task volume and Monitor spool."""

from __future__ import annotations

import json
import hashlib
import errno
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.docker_tool import DockerToolPort


SCHEMA = 'pilot-analysis-spool-v1'


def _atomic_json(path: Path, value: dict) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PilotDockerToolPort(DockerToolPort):
    """Reuse the certified session/byte/receipt logic with fixed live mounts."""

    def __init__(self, *, image, task_volume, trusted_root, cognition_root,
                 scratch_root, evidence_root):
        self.image = str(image)
        self.task_volume = str(task_volume)
        self.private = Path(trusted_root).resolve(strict=True)
        self.cognition = Path(cognition_root).resolve(strict=True)
        self.scratch = Path(scratch_root).resolve(strict=True)
        self.evidence = Path(evidence_root).resolve(strict=True)
        if not all(path.is_dir() for path in (self.private, self.cognition,
                                              self.scratch, self.evidence)):
            raise ValueError('Pilot analysis roots are missing')
        if any(self.private == writable or self.private.is_relative_to(writable)
               for writable in (self.cognition, self.scratch)):
            raise ValueError('Trusted analysis root must be outside writable model roots')
        for name in ('home', 'tmp', 'build_cache', 'output'):
            (self.scratch / name).mkdir(parents=True, exist_ok=True)
        self._mount_identities = {str(path): self._safe_mount_identity(path)
                                  for path in (self.private, self.cognition, self.scratch,
                                               self.evidence, *(self.scratch / name for name in
                                                                ('home', 'tmp', 'build_cache', 'output')))}
        self.new_sessions = {}
        self.historical = {}
        image_result = subprocess.run(['docker', 'image', 'inspect', self.image, '--format', '{{.Id}}'],
                                      text=True, capture_output=True, timeout=20)
        volume_result = subprocess.run(['docker', 'volume', 'inspect', self.task_volume,
                                        '--format', '{{.Name}}'],
                                       text=True, capture_output=True, timeout=20)
        if (image_result.returncode != 0 or image_result.stdout.strip() != self.image or
                volume_result.returncode != 0 or volume_result.stdout.strip() != self.task_volume):
            raise ValueError('Pinned pilot image or Task volume identity mismatch')

    @staticmethod
    def _safe_mount_identity(path):
        if path.is_symlink() or getattr(os.path, 'isjunction', lambda _: False)(path):
            raise RuntimeError('Pilot mount source is redirected')
        resolved = path.resolve(strict=True)
        if resolved != path or not path.is_dir():
            raise RuntimeError('Pilot mount source identity changed')
        stat = path.stat()
        return (stat.st_dev, stat.st_ino)

    def _check_mount_sources(self):
        for text, identity in self._mount_identities.items():
            if self._safe_mount_identity(Path(text)) != identity:
                raise RuntimeError('Pilot mount source identity changed')

    def _docker_args(self, session: str, script: Path, kind: str) -> list[str]:
        self._check_mount_sources()
        interpreter = {'python': '/usr/bin/python3', 'bash': '/bin/bash'}[kind]
        virtual_script = '/pilot_control/' + script.relative_to(self.private).as_posix()
        scratch = self.scratch
        return ['docker', 'run', '--rm', '--name', session, '--network', 'none',
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--mount', f'type=volume,source={self.task_volume},destination=/app,readonly',
                '--mount', f'type=bind,source={self.private},destination=/pilot_control,readonly',
                '--mount', f'type=bind,source={self.cognition},destination=/logs/agent/monitor/monitor_private,readonly',
                '--mount', f'type=bind,source={self.evidence},destination=/logs/agent/monitor/task_evidence,readonly',
                '--mount', f'type=bind,source={scratch / "home"},destination=/home/monitor',
                '--mount', f'type=bind,source={scratch / "tmp"},destination=/tmp',
                '--mount', f'type=bind,source={scratch / "build_cache"},destination=/cache',
                '--mount', f'type=bind,source={scratch / "output"},destination=/output',
                '--env', 'HOME=/home/monitor', '--env', 'TMPDIR=/tmp',
                '--env', 'GOCACHE=/cache/go', '--env', 'GOPROXY=off',
                '--entrypoint', interpreter, self.image, virtual_script]

    def mirror_output(self, session):
        """Expose a read-only-in-diagnostic copy; trusted original stays private."""
        source = self.private / 'audit' / 'commands' / session / 'output.log'
        if not source.is_file() or source.is_symlink():
            raise RuntimeError('Trusted analysis output unavailable')
        destination = self.cognition / 'audit' / 'commands' / session / 'output.log'
        if destination.exists() and destination.is_symlink():
            raise RuntimeError('Analysis output mirror redirected')
        destination.parent.mkdir(parents=True, exist_ok=True)
        staged = destination.with_name('output.pending')
        if staged.exists():
            raise RuntimeError('Analysis output mirror pending file exists')
        shutil.copyfile(source, staged)
        os.replace(staged, destination)

    def close(self):
        primary_error = None
        try:
            super().close()
        except Exception as exc:
            primary_error = exc
        for session in self.new_sessions:
            entry = self.new_sessions[session]
            process = entry.get('process')
            if process is not None and process.poll() is None:
                # Attempt exact-session cleanup even after a watcher failure.
                subprocess.run(['docker', 'rm', '-f', session], text=True,
                               capture_output=True, timeout=15)
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError('cleanup_unknown: analysis writer still running') from exc
            try:
                found = subprocess.run(['docker', 'inspect', session], text=True,
                                       capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError('cleanup_unknown: Docker inspect unavailable') from exc
            if found.returncode == 0:
                raise RuntimeError('Pilot analysis container deletion unconfirmed')
            if 'no such object' not in found.stderr.lower():
                raise RuntimeError('cleanup_unknown: Docker inspect did not certify absence')
            try:
                daemon = subprocess.run(['docker', 'info', '--format', '{{.ID}}'], text=True,
                                        capture_output=True, timeout=15)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RuntimeError('cleanup_unknown: Docker daemon unavailable') from exc
            if daemon.returncode != 0 or not daemon.stdout.strip():
                raise RuntimeError('cleanup_unknown: Docker daemon state unconfirmed')
            if entry.get('reason') == 'cleanup_error':
                raise RuntimeError('cleanup_unknown: session watcher reported cleanup_error')
        if primary_error is not None:
            raise RuntimeError('cleanup_unknown: base session cleanup failed') from primary_error


class PilotHostBridge:
    def __init__(self, *, root, run_id, port: PilotDockerToolPort, adopt_existing=False):
        self.root = Path(root).resolve()
        self.run_id = str(run_id)
        self.port = port
        self.closed = False
        self._session_scratch_before = {}
        if adopt_existing:
            expected = {'schema': SCHEMA, 'run_id': self.run_id}
            identity = json.loads((self.root / 'identity.json').read_text(encoding='utf-8'))
            if identity != expected or any(not (self.root / name).is_dir()
                                           for name in ('requests', 'accepted', 'responses')):
                raise RuntimeError('Existing pilot spool identity mismatch')
        else:
            self.root.mkdir(parents=True, exist_ok=False)
            for name in ('requests', 'accepted', 'responses'):
                (self.root / name).mkdir()
            _atomic_json(self.root / 'identity.json', {'schema': SCHEMA, 'run_id': self.run_id})

    def _handle(self, request):
        if request.get('schema') != SCHEMA or request.get('run_id') != self.run_id:
            raise RuntimeError('Analysis request ownership mismatch')
        op = request.get('operation')
        common = {'schema', 'run_id', 'request_id', 'operation'}
        if op == 'start':
            if set(request) != common | {'code', 'code_type', 'timeout', 'wait_seconds'}:
                raise ValueError('Analysis start fields mismatch')
            before = self._scratch_snapshot()
            result = self.port.execute('code_run', {
                'code': request['code'], 'type': request['code_type'],
                'timeout': request['timeout'], 'wait_seconds': request['wait_seconds']})
            if result.get('session_id'):
                self.port.mirror_output(result['session_id'])
            result['source_version'] = {'status': 'version_uncertain',
                                        'task_volume': self.port.task_volume}
            if result.get('session_id'):
                self._session_scratch_before[result['session_id']] = before
            result['private_scratch_diff_at_return'] = self._scratch_diff(before, self._scratch_snapshot())
            return result
        if op == 'read':
            if set(request) != common | {'session_id', 'wait_seconds', 'cancel'}:
                raise ValueError('Analysis read fields mismatch')
            result = self.port.execute('code_run', {
                'session_id': request['session_id'], 'wait_seconds': request['wait_seconds'],
                'cancel': request['cancel']})
            if result.get('session_id'):
                self.port.mirror_output(result['session_id'])
            result['source_version'] = {'status': 'version_uncertain',
                                        'task_volume': self.port.task_volume}
            before = self._session_scratch_before.get(request['session_id'])
            if before is not None and result.get('status') != 'running':
                result['private_scratch_diff'] = self._scratch_diff(before, self._scratch_snapshot())
            return result
        if op == 'close' and set(request) == common:
            self.port.close()
            self.closed = True
            return {'status': 'closed'}
        raise ValueError('Unsupported analysis operation')

    def _scratch_snapshot(self):
        # Source identity remains a hard gate; optional statistics do not own
        # the execution receipt after a command has already run.
        self.port._check_mount_sources()
        try:
            return self._scratch_files()
        except OSError as exc:
            return {'files': {}, 'skipped': [{'path': str(getattr(exc, 'filename', None)),
                                              'reason': type(exc).__name__}],
                    'snapshot_incomplete': True, 'limit_reached': False}

    def _scratch_files(self):
        root = self.port.scratch
        files, skipped = {}, []
        started = time.monotonic()
        limit = 20000
        for name in ('tmp', 'output'):
            def vanished(exc):
                if exc.errno in (errno.ENOENT, errno.ENOTDIR):
                    skipped.append({'path': str(exc.filename), 'reason': 'disappeared'})
                else:
                    raise exc
            for directory, dirs, names in os.walk(root / name, onerror=vanished):
                if time.monotonic() - started > 5 or len(files) + len(skipped) >= limit:
                    return {'files': files, 'skipped': skipped,
                            'snapshot_incomplete': True, 'limit_reached': True}
                for filename in names:
                    if time.monotonic() - started > 5 or len(files) + len(skipped) >= limit:
                        return {'files': files, 'skipped': skipped,
                                'snapshot_incomplete': True, 'limit_reached': True}
                    path = Path(directory) / filename
                    relative = path.relative_to(root).as_posix()
                    try:
                        if path.is_symlink() or not path.is_file():
                            continue
                        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
                    except OSError as exc:
                        if exc.errno not in (errno.ENOENT, errno.ENOTDIR):
                            raise
                        skipped.append({'path': relative, 'reason': 'disappeared'})
        return {'files': files, 'skipped': skipped,
                'snapshot_incomplete': bool(skipped), 'limit_reached': False}

    @staticmethod
    def _scratch_diff(before, after):
        old, new = before['files'], after['files']
        return {'added': sorted(new.keys() - old.keys()),
                'changed': sorted(path for path in new.keys() & old.keys()
                                  if new[path] != old[path]),
                'removed': sorted(old.keys() - new.keys()),
                'snapshot_incomplete': before['snapshot_incomplete'] or after['snapshot_incomplete'],
                'skipped_before': before['skipped'], 'skipped_after': after['skipped'],
                'limit_reached': before['limit_reached'] or after['limit_reached']}

    def serve_once(self):
        for request_path in sorted((self.root / 'requests').glob('*.json')):
            if self.closed:
                break
            request_id = request_path.stem
            receipt_path = self.root / 'responses' / request_path.name
            if receipt_path.exists():
                continue
            accepted = self.root / 'accepted' / request_path.name
            if accepted.exists():
                # The previous host may have executed. Never submit again.
                _atomic_json(receipt_path, {'run_id': self.run_id, 'request_id': request_id,
                                            'status': 'uncertain', 'result': None})
                continue
            request = json.loads(request_path.read_text(encoding='utf-8'))
            if request.get('request_id') != request_id:
                raise ValueError('Analysis request filename/ID mismatch')
            _atomic_json(accepted, {'run_id': self.run_id, 'request_id': request_id,
                                    'accepted_at_ns': time.time_ns()})
            try:
                result = self._handle(request)
                receipt = {'run_id': self.run_id, 'request_id': request_id,
                           'status': 'ok', 'result': result}
            except (ValueError, KeyError) as exc:
                # Invalid model arguments are a tool error, not a new process.
                receipt = {'run_id': self.run_id, 'request_id': request_id,
                           'status': 'ok', 'result': {'status': 'error', 'error': str(exc)}}
            _atomic_json(receipt_path, receipt)

    def close(self):
        if not self.closed:
            self.port.close()
            self.closed = True
