"""Authority-gated host-static batch; never runs a Task or native evaluator."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import requests
import subprocess
import sys
import time

from monitor_agent_core.provider import ProviderRecoveryExhausted
from monitor_agent_core.loop import MonitorLoopError
from monitor_agent_core.analysis_spool import AnalysisPortIntegrityError
from monitor_agent_core.evidence_package_v1 import EvidencePackageIntegrityError

from .static_session import StaticDiagnosticSession, _canonical
from .static_host import IMAGE
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_profile import (
    public_profile_identity, resolved_supervisor_profile)


ORDER = [('C01', 'R1', 'N'), ('C01', 'R1', 'E'), ('C02', 'R1', 'E'),
         ('C02', 'R1', 'N'), ('C01', 'R2', 'E'), ('C01', 'R2', 'N'),
         ('C02', 'R2', 'N'), ('C02', 'R2', 'E'), ('C01', 'R3', 'N'),
         ('C01', 'R3', 'E'), ('C02', 'R3', 'E'), ('C02', 'R3', 'N')]
SLOTS = [{'order': i, 'scene': scene, 'repeat': repeat, 'condition': condition}
         for i, (scene, repeat, condition) in enumerate(ORDER, 1)]
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REQUIRED_SOURCE = {
    'GenericAgent-main/monitor_agent_core/agent.py',
    'GenericAgent-main/monitor_agent_core/evidence_package_v1.py',
    'GenericAgent-main/monitor_agent_core/provider.py',
    'method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012/static_session.py',
    'method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012/static_host.py',
    'method_discovery/curator_supervisor_convergence_v0/evidence_package_v1_20261012/static_live_batch.py',
    'method_discovery/curator_supervisor_convergence_v0/real_task_effect_pilot_preflight_20261010/pilot_profile.py',
}
CUTOFFS = {
    'C01': {'public_cursor': 120, 'task_turn': 61, 'ordinary_files': 2472,
            'workspace_tree_sha256': '88b7f94d499368196bc8ac1870da4491769598eb4ce567b8c6e12a10bf289a0b',
            'public_prefix_sha256': 'c5256026bca46e13118dccd50aa0dd00c5e2493aba39e0cac8dc4ecd6cb91382',
            'book_sha256': 'f6f070f65896a81ba3eeda1b9034b9eb34f23627099e5356e2bde24d24c77355',
            'completion_pending': False},
    'C02': {'public_cursor': 161, 'task_turn': 83, 'ordinary_files': 2476,
            'workspace_tree_sha256': '40acbedf3c03d863cac8514298618f74ca999c706466dc426ae8eb638708d2f0',
            'public_prefix_sha256': 'f2a007c9afa3ed8d097e249d6b96d55717066d61217c1229f823764bb6ad9441',
            'book_sha256': 'f6f070f65896a81ba3eeda1b9034b9eb34f23627099e5356e2bde24d24c77355',
            'completion_pending': True},
}


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _head() -> str:
    result = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO,
                            capture_output=True, text=True, timeout=10, check=True)
    return result.stdout.strip()


def _profile(path: Path, condition: str) -> dict:
    profiles = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(profiles) != {'claude_monitor_opus48'}:
        raise RuntimeError('Authorized Supervisor profile set differs')
    config = resolved_supervisor_profile(profiles['claude_monitor_opus48'],
        variant='narrow_v1' if condition == 'N' else 'evidence_package_v1')
    public = public_profile_identity(config)
    public['monitor_evidence_package_v1'] = config.get('monitor_evidence_package_v1', False)
    if (config.get('provider') != 'anthropic' or config.get('model') != 'claude-opus-4-8'
            or config.get('max_tokens') != 8192 or config.get('max_retries') != 0
            or config.get('incomplete_stream_recovery_v1') is not True
            or config.get('verify') is not True or
            config.get('temperature', 1) != 1):
        raise RuntimeError('Static batch provider profile does not match frozen contract')
    return config, public


def validate_gate(manifest_path: Path, auth_path: Path, profile_path: Path,
                  output_root: Path, *, require_fresh: bool) -> tuple[dict, dict]:
    manifest = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    auth = json.loads(Path(auth_path).read_text(encoding='utf-8'))
    if (manifest.get('execution_authorized') is not False or
            manifest.get('slots') != SLOTS or
            manifest.get('cutoffs') != CUTOFFS or
            manifest.get('image_id') != IMAGE or
            manifest.get('max_outer_cycles') != 100 or
            manifest.get('deadline_seconds') != 3600 or
            manifest.get('profile_sha256') != digest(profile_path) or
            auth.get('execution_authorized') is not True or
            auth.get('manifest_sha256') != digest(manifest_path) or
            auth.get('audited_code_commit') != _head() or
            auth.get('approved_slots') != SLOTS or
            Path(auth.get('output_root', '')).resolve() != output_root.resolve() or
            require_fresh and output_root.exists()):
        raise RuntimeError('Static batch authorization or frozen identity mismatch')
    bindings = auth.get('run_bindings')
    if (not isinstance(bindings, list) or len(bindings) != 12 or
            [item.get('order') for item in bindings] != list(range(1, 13)) or
            len({item.get('run_id') for item in bindings}) != 12 or
            any(item.get('scene') != slot['scene'] or
                item.get('condition') != slot['condition'] or
                item.get('repeat') != slot['repeat'] or
                Path(item.get('run_root', '')).resolve() !=
                (output_root / f"{slot['order']:02d}-{slot['scene']}-{slot['repeat']}-{slot['condition']}").resolve()
                for item, slot in zip(bindings, SLOTS))):
        raise RuntimeError('Static batch run bindings differ')
    for condition in ('N', 'E'):
        _, public = _profile(profile_path, condition)
        if manifest.get('public_profiles', {}).get(condition) != public:
            raise RuntimeError('Static batch public profile differs')
    if set(manifest.get('source_sha256', {})) != REQUIRED_SOURCE:
        raise RuntimeError('Static batch source manifest incomplete')
    for relative, expected in manifest['source_sha256'].items():
        path = (REPO / relative).resolve()
        if not path.is_file() or not path.is_relative_to(REPO) or digest(path) != expected:
            raise RuntimeError('Static batch source identity differs')
    return manifest, auth


class _ArchivedResponse:
    def __init__(self, response, path: Path):
        self.response = response
        self.path = path
        self.stream = None

    def __enter__(self):
        self.response.__enter__()
        self.stream = self.path.open('x', encoding='ascii')
        return self

    def __exit__(self, *exc):
        try:
            if self.stream is not None:
                self.stream.close()
        finally:
            return self.response.__exit__(*exc)

    def __getattr__(self, name):
        return getattr(self.response, name)

    def iter_lines(self):
        for index, line in enumerate(self.response.iter_lines()):
            raw = line if isinstance(line, bytes) else str(line).encode('utf-8')
            self.stream.write(json.dumps({'index': index, 'monotonic': time.monotonic(),
                'base64': base64.b64encode(raw).decode('ascii')}) + '\n')
            self.stream.flush()
            yield line


def archived_sender(session: StaticDiagnosticSession):
    """Archive the existing requests.post response lines, without logging headers/URL."""
    def send(url, **kwargs):
        request_id = session.client._progress_request_id
        if not request_id or not isinstance(request_id, str):
            raise RuntimeError('Missing provider request identity')
        path = session.capture_root / (request_id + '.sse.jsonl')
        if path.exists():
            raise RuntimeError('SSE archive would be overwritten')
        return _ArchivedResponse(requests.post(url, **kwargs), path)
    return send


def run_slot(slot: dict, binding: dict, config: dict, *, fake_sender=None) -> dict:
    destination = Path(binding['run_root'])
    if destination.exists():
        raise RuntimeError('Static slot destination already exists')
    started = time.time()
    condition = 'N' if slot['condition'] == 'N' else 'evidence_package_v1'
    session = None
    error = None
    cleanup_error = None
    result = None
    try:
        session = StaticDiagnosticSession(slot['scene'], destination, condition=condition,
            deadline_seconds=3600, _live_config=config)
        cutoff = CUTOFFS[slot['scene']]
        if (session.manifest['ordinary_files'] != cutoff['ordinary_files'] or
                session.manifest['workspace_tree_sha256'] != cutoff['workspace_tree_sha256'] or
                any(session.cutoff[key] != cutoff[key] for key in
                    ('public_cursor', 'task_turn', 'completion_pending',
                     'public_prefix_sha256', 'book_sha256'))):
            raise RuntimeError('Static cutoff material differs before model send')
        session.client.transport_post = (fake_sender if fake_sender is not None
                                         else archived_sender(session))
        result = session.review(max_turns=100)
    except BaseException as exc:
        error = exc
    finally:
        if session is not None:
            try:
                session.close()
            except BaseException as exc:
                cleanup_error = exc
    def scrub(exc):
        if exc is None:
            return None
        message = str(exc)
        for secret in (str(config.get('apikey') or ''), str(config.get('apibase') or '')):
            if secret:
                message = message.replace(secret, '[REDACTED]')
        return message
    def chain(exc):
        result = []
        seen = set()
        while exc is not None and id(exc) not in seen:
            seen.add(id(exc))
            result.append({'type': type(exc).__name__, 'message': scrub(exc)})
            exc = exc.__cause__ or exc.__context__
        return result
    causes = []
    cause = error
    while cause is not None and cause not in causes:
        causes.append(cause)
        cause = cause.__cause__ or cause.__context__
    integrity_failure = any(isinstance(item, (AnalysisPortIntegrityError,
                            EvidencePackageIntegrityError)) for item in causes)
    local = (isinstance(error, (ProviderRecoveryExhausted, MonitorLoopError))
             and not integrity_failure)
    counts = {}
    archive_error = None
    if session is not None:
        paths = {'provider': session.capture_root / 'provider_events.jsonl',
                 'dialogue': (session.monitor.evidence_host_audit_root / 'dialogue.jsonl'
                              if session.monitor.evidence_package_v1 else
                              session.port.cognition / 'audit' / 'dialogue.jsonl')}
        try:
            for key, path in paths.items():
                if not path.is_file():
                    raise RuntimeError('Required static ' + key + ' event archive missing')
                for line in path.read_text(encoding='utf-8').splitlines():
                    event = json.loads(line).get('event')
                    name = key + ':' + str(event)
                    counts[name] = counts.get(name, 0) + 1
        except Exception as exc:
            archive_error = exc
    record = {'slot': slot, 'run_id': binding['run_id'], 'started_unix': started,
        'ended_unix': time.time(), 'outcome': result,
        'error_type': type(error).__name__ if error else None,
        'error': scrub(error),
        'error_chain': chain(error),
        'integrity_failure': integrity_failure,
        'cleanup_error_type': type(cleanup_error).__name__ if cleanup_error else None,
        'cleanup_error': scrub(cleanup_error),
        'cleanup_error_chain': chain(cleanup_error),
        'archive_error_type': type(archive_error).__name__ if archive_error else None,
        'archive_error': scrub(archive_error),
        'cleanup_certified': session is not None and cleanup_error is None,
        'stop_batch': cleanup_error is not None or archive_error is not None or
                      (error is not None and not local),
        'complete_calls': session.client.complete_calls if session else 0,
        'pre_send_attempts': session.request_count if session else 0,
        'mechanical_event_counts': counts}
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / 'SLOT_RESULT.json'
    if path.exists():
        raise RuntimeError('Slot result would be overwritten')
    path.write_bytes(_canonical(record))
    return record


def finish_archive(root: Path) -> None:
    """Index all retained bytes; no evaluator or Task process is invoked."""
    result = json.loads((root / 'BATCH_RESULT.json').read_text(encoding='utf-8'))
    manifest = json.loads((root / 'MANIFEST_USED.json').read_text(encoding='utf-8'))
    text = ('STATIC EVIDENCE-PACKAGE DIAGNOSTIC BATCH - MECHANICAL AUDIT\n'
            'Task, native evaluator, scorer and training were not launched.\n'
            'Controls are simulated=true/input_sent=false.\n'
            'The static scenes are known exposed Fyne checkpoints, not independent tasks.\n'
            'No diagnostic quality judgment is made here.\n\n'
            'MANIFEST\n' + json.dumps(manifest, ensure_ascii=False, indent=2) +
            '\n\nBATCH RESULT\n' + json.dumps(result, ensure_ascii=False, indent=2) +
            '\nAll listed raw files remain individually readable under this run root.\n')
    (root / 'STATIC_BATCH_AUDIT.txt').write_text(text, encoding='utf-8')
    rows = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.name == 'RAW_FILE_INDEX.json':
            continue
        relative = path.relative_to(root).as_posix()
        rows.append({'path': relative, 'bytes': path.stat().st_size,
                     'sha256': digest(path)})
    (root / 'RAW_FILE_INDEX.json').write_bytes(_canonical(rows))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--profile-file', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--child-order', type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.live:
        raise RuntimeError('Static batch live entry is authorization-gated')
    _, auth = validate_gate(args.manifest, args.authorization, args.profile_file,
                            args.output_root, require_fresh=args.child_order is None)
    if args.child_order is not None:
        started = args.output_root / 'BATCH_STARTED.json'
        if not started.is_file() or (args.output_root / 'BATCH_RESULT.json').exists():
            raise RuntimeError('Static child is not inside one active authorized batch')
        identity = json.loads(started.read_text(encoding='utf-8'))
        if (identity.get('manifest_sha256') != digest(args.manifest) or
                identity.get('authorization_sha256') != digest(args.authorization)):
            raise RuntimeError('Static child parent authorization identity differs')
        slot = SLOTS[args.child_order - 1]
        binding = auth['run_bindings'][args.child_order - 1]
        config, _ = _profile(args.profile_file, slot['condition'])
        run_slot(slot, binding, config)
        return
    args.output_root.mkdir(parents=True)
    (args.output_root / 'BATCH_STARTED.json').write_bytes(_canonical({
        'manifest_sha256': digest(args.manifest),
        'authorization_sha256': digest(args.authorization),
        'code_commit': _head(), 'started_unix': time.time()}))
    (args.output_root / 'AUTHORIZATION_USED.json').write_bytes(args.authorization.read_bytes())
    (args.output_root / 'MANIFEST_USED.json').write_bytes(args.manifest.read_bytes())
    batch = []
    original_auth_sha = digest(args.authorization)
    try:
        for slot, binding in zip(SLOTS, auth['run_bindings']):
            command = [sys.executable, '-m', __package__ + '.static_live_batch', '--live',
                '--manifest', str(args.manifest), '--authorization', str(args.authorization),
                '--profile-file', str(args.profile_file), '--output-root', str(args.output_root),
                '--child-order', str(slot['order'])]
            child = subprocess.run(command, cwd=REPO, capture_output=True)
            prefix = args.output_root / f"{slot['order']:02d}-{slot['scene']}-{slot['repeat']}-{slot['condition']}"
            prefix.mkdir(parents=True, exist_ok=True)
            (prefix / 'child_stdout.txt').write_bytes(child.stdout)
            (prefix / 'child_stderr.txt').write_bytes(child.stderr)
            path = prefix / 'SLOT_RESULT.json'
            if not path.is_file():
                batch.append({'slot': slot, 'stop_batch': True, 'error': 'missing_slot_result'})
                break
            record = json.loads(path.read_text(encoding='utf-8'))
            batch.append(record)
            if child.returncode or record['stop_batch'] or not record['cleanup_certified']:
                break
    finally:
        try:
            (args.output_root / 'BATCH_RESULT.json').write_bytes(_canonical({
                'slots': batch, 'planned': SLOTS, 'started_count': len(batch)}))
            finish_archive(args.output_root)
        finally:
            if args.authorization.is_file() and digest(args.authorization) == original_auth_sha:
                args.authorization.unlink()


if __name__ == '__main__':
    main()
