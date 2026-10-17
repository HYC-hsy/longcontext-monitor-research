"""One authorized synthetic live-protocol check; no Task tools or evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'GenericAgent-main'))
sys.path.insert(0, str(HERE / 'vendor'))

import llmcore
from .episode import PoSEpisode, execution_config
from .single_manifest import CHECKOUT, source_hashes, vendor_hashes
from .worker import (RoleTransport, ROLE_JSON_CONTRACT_VERSION,
                     ROLE_INPUT_CONTRACT_VERSION, ROLE_OBJECT_INSTRUCTION,
                     ROLE_UPDATE_FIELDS_INSTRUCTION, ROLE_MAX_TOKENS,
                     ROLE_TEMPERATURE, ROLE_THINKING_TYPE)


def generation_identity():
    return {'role_max_tokens': ROLE_MAX_TOKENS,
        'role_thinking_type': ROLE_THINKING_TYPE,
        'role_temperature': ROLE_TEMPERATURE,
        'role_json_contract': ROLE_JSON_CONTRACT_VERSION,
        'role_input_contract': ROLE_INPUT_CONTRACT_VERSION,
        'role_object_instruction': ROLE_OBJECT_INSTRUCTION,
        'role_update_fields_instruction': ROLE_UPDATE_FIELDS_INSTRUCTION,
        'role_transport_retries': 0}


def compatibility_checks(rows, result, initial, updated, wire, roles,
                         *, work_finished):
    """Judge final original-core outcomes, not a transient parse error or HTTP 200."""
    def has(event, step=None, operation=None):
        return any(row.get('event') == event and
                   (step is None or row.get('step') == step) and
                   (operation is None or row.get('operation') == operation)
                   for row in rows)
    audit_submitted = [row for row in rows if
        row.get('event') == 'belief_sentinel_audit_submitted' and row.get('step') == 0]
    audit_completed = [row for row in rows if
        row.get('event') == 'belief_sentinel_audit_completed' and row.get('step') == 0]
    audit_failed = [row for row in rows if
        row.get('event') == 'belief_sentinel_audit_failed' and row.get('step') == 0]
    transitions = result.get('health_transitions') or []
    progress = transitions[-1].get('progress') if len(transitions) == 1 else None
    checks = {
        'initial_original_parse_committed': has('belief_model_response', -1, 'initialize')
            and has('belief_state_initialized', -1) and bool(initial.get('belief_text')),
        'update_original_parse_resolved': has('belief_model_response', 0, 'update')
            and has('belief_candidate_generated', 0)
            and has('belief_state_updated', 0)
            and len([item for item in result.get('belief_update_history') or []
                     if item.get('step') == 0 and item.get('status') in
                     {'validated', 'repaired', 'rejected'}]) == 1,
        'sentinel_final_audit_resolved': bool(audit_submitted)
            and len(audit_completed) == len(audit_submitted)
            and not audit_failed
            and len((result.get('belief_sentinel') or {}).get('audit_history') or [])
                >= len(audit_completed),
        'final_textualization': has('belief_model_response', 0, 'textualize')
            and has('belief_text_updated', 0) and bool(updated.get('belief_text')),
        'valid_nonterminal_progress': has('belief_sentinel_progress_completed', 0)
            and has('belief_transition_progress_applied', 0)
            and progress in (0, 1) and not isinstance(progress, bool)
            and result.get('scored_transitions') == 1,
        'applicable_work_finished': work_finished,
        'role_and_transport_protocol': {'belief', 'consistency', 'progress'} <= set(roles)
            and bool(wire) and all(row.get('http_status') == 200 and
                row.get('returned_model') == 'claude-opus-4-8' and
                row.get('stop_reason') not in {None, 'max_tokens'} for row in wire),
    }
    return {'status': 'passed' if all(checks.values()) else 'failed',
            'checks': checks, 'audit_submitted': len(audit_submitted),
            'audit_completed': len(audit_completed),
            'audit_failed': len(audit_failed), 'transition_progress': progress}


def safe_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write('\n')


class PublicLogger:
    def __init__(self, path):
        self.path = path
        self.stream = path.open('x', encoding='utf-8', newline='\n')
        self.events = []
        self.rows = []
    def log(self, event, **data):
        # Transport exception text can contain a private endpoint. The type,
        # role, stage and attempted HTTP status remain sufficient here.
        data.pop('error', None)
        self.events.append((event, data.get('operation')))
        row = {'event': event, **data}
        self.rows.append(row)
        self.stream.write(json.dumps(row,
                                     ensure_ascii=False, default=str) + '\n')
        self.stream.flush()
    def close(self):
        self.stream.close()


class ResponseTap:
    def __init__(self, response, row):
        self.response, self.row = response, row
    def __enter__(self):
        self.response.__enter__()
        return self
    def __exit__(self, *args):
        return self.response.__exit__(*args)
    def __getattr__(self, name):
        return getattr(self.response, name)
    def iter_lines(self, *args, **kwargs):
        for line in self.response.iter_lines(*args, **kwargs):
            if isinstance(line, bytes) and line.startswith(b'data: '):
                try:
                    data = json.loads(line[6:])
                    model = (data.get('message') or {}).get('model')
                    if model:
                        self.row['returned_model'] = model
                    if data.get('type') in {'message_start', 'message_delta'}:
                        usage = (data.get('message') or {}).get('usage') if (
                            data.get('type') == 'message_start') else data.get('usage')
                        if isinstance(usage, dict):
                            self.row.setdefault('usage_events', []).append(usage)
                    if data.get('type') == 'message_delta':
                        self.row['stop_reason'] = (data.get('delta') or {}).get('stop_reason')
                except (ValueError, AttributeError):
                    pass
            yield line
    def json(self):
        value = self.response.json()
        if isinstance(value, dict) and value.get('model'):
            self.row['returned_model'] = value['model']
        return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-file', type=Path, required=True)
    parser.add_argument('--scope', type=Path, required=True)
    parser.add_argument('--certification', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from .certification import verify_evidence
    certified = verify_evidence(args.certification.resolve(strict=True))
    if certified.get('status') != 'pass':
        raise RuntimeError('current committed synthetic certification failed')
    scope_path = args.scope.resolve(strict=True)
    scope = json.loads(scope_path.read_text(encoding='utf-8'))
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=CHECKOUT,
        capture_output=True, text=True, check=True).stdout.strip()
    profile_path = args.profile_file.resolve(strict=True)
    profile = runpy.run_path(str(profile_path))['native_claude_cc_vibe_opus48']
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    generation = generation_identity()
    if (scope.get('schema') != 'pos-ga-user-authorized-serial-scope-v1' or
            scope.get('code_commit') != head or
            scope.get('source_files_sha256') != source_hashes() or
            scope.get('vendor_files_sha256') != vendor_hashes() or
            scope.get('certification_sha256') != sha(
                args.certification / 'FILE_HASHES.json') or
            scope.get('role_generation') != generation or
            len(scope.get('prepared', [])) != 4 or
            any(row.get('profile_sha256') != sha(profile_path)
                for row in scope['prepared']) or
            profile.get('model') != 'claude-opus-4-8'):
        raise RuntimeError('compatibility scope, code, certification or profile differs')
    root = args.output.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    identity = {'schema': 'pos-ga-live-compatibility-v3',
        'scope_sha256': sha(scope_path), 'code_commit': head,
        'source_files_sha256': source_hashes(),
        'vendor_files_sha256': vendor_hashes(),
        'certification_sha256': scope['certification_sha256'],
        'role_generation': scope['role_generation'],
        'profile_sha256': sha(profile_path),
        'probe_sha256': sha(__file__),
        'serial_sha256': sha(HERE / 'serial_live.py'),
        'model_requested': profile['model'], 'task_tools_executed': 0,
        'official_evaluator_calls': 0}
    safe_json(root / 'identity.json', identity)
    logger = PublicLogger(root / 'role_events.jsonl')
    wire = []
    phase = {'name': 'pos_reset_update'}
    original_post = llmcore.requests.post
    def post(url, **kwargs):
        row = {'phase': phase['name'], 'attempt': len(wire) + 1,
               'model_visible_payload': {k: v for k, v in kwargs['json'].items()
                                         if k != 'metadata'},
               'http_status': None, 'returned_model': None,
               'usage_events': [], 'stop_reason': None}
        wire.append(row)
        try:
            response = original_post(url, **kwargs)
            row['http_status'] = response.status_code
            return ResponseTap(response, row)
        except BaseException as error:
            row['error_type'] = type(error).__name__
            raise
    llmcore.requests.post = post
    report = {'schema': 'pos-ga-live-compatibility-result-v3',
              'status': 'failed', 'phase': phase['name'],
              'identity': identity, 'task_logical_calls': 0, 'pos_logical_calls': 0,
              'task_tools_executed': 0, 'official_evaluator_calls': 0,
              'historical_task_protocol': 'raw_compat_v1; not repeated'}
    transport = None
    episode = None
    try:
        transport = RoleTransport(mode='profile', profile=profile, archive=logger)
        episode = PoSEpisode(case_id='synthetic-compatibility',
            config=execution_config(), logger=logger,
            belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        initial_context = episode.reset(task='SYNTHETIC GOAL: inspect a marked item once.',
            observation='SYNTHETIC INITIAL OBSERVATION: item state unknown.',
            actions=[{'name': 'probe', 'description': 'Synthetic observation marker; not executed.'}])
        update_context = episode.update(thought='Synthetic inspection decision.',
            action_batch=[{'id': 'synthetic-action-1', 'name': 'probe',
                           'arguments': {}, 'order': 0,
                           'status': 'synthetic_observation_only'}],
            observation='SYNTHETIC PUBLIC OBSERVATION: marker is visible; '
                        'no real environment action occurred.', done=False)
        episode.manager.close()
        report['pos_logical_calls'] = len(transport.calls)
        report['pos_roles'] = [row['role'] for row in transport.calls]
        report['pos_result'] = episode.get_result()
        report['initial_context'] = initial_context
        report['update_context'] = update_context
        report['compatibility_checks'] = compatibility_checks(
            logger.rows, report['pos_result'], initial_context, update_context,
            wire, report['pos_roles'],
            work_finished=bool(episode.manager.sentinel and
                               episode.manager.sentinel.closed))
        if report['compatibility_checks']['status'] != 'passed':
            raise RuntimeError('final original PoS protocol/stage incomplete')
        report['status'] = 'passed'
    except BaseException as error:
        report['phase'] = phase['name']
        report['error_type'] = type(error).__name__
    finally:
        llmcore.requests.post = original_post
        if episode is not None and report['status'] != 'passed':
            try:
                report['partial_pos_result'] = episode.get_result()
            except BaseException as error:
                report['partial_pos_result_error_type'] = type(error).__name__
        if transport is not None:
            report['pos_logical_calls'] = len(transport.calls)
            report['pos_roles'] = [row['role'] for row in transport.calls]
        report['http_attempts'] = len(wire)
        report['returned_models'] = [row.get('returned_model') for row in wire]
        report['role_adapter_events'] = sum(event == 'pos_role_json_adapter'
            for event, _ in logger.events)
        report['role_parse_error_events'] = sum(event.endswith('_parse_error')
            for event, _ in logger.events)
        logger.close()
        safe_json(root / 'http_attempts.json', wire)
        report['role_events_sha256'] = sha(root / 'role_events.jsonl')
        report['http_attempts_sha256'] = sha(root / 'http_attempts.json')
        safe_json(root / 'result.json', report)
    print(json.dumps({'status': report['status'], 'phase': report['phase'],
        'task_logical_calls': report['task_logical_calls'],
        'pos_logical_calls': report['pos_logical_calls'],
        'http_attempts': report['http_attempts'],
        'error_type': report.get('error_type')}, ensure_ascii=False))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
