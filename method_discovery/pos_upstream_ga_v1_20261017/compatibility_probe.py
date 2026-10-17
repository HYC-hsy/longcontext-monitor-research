"""One authorized synthetic live-protocol check; no Task tools or evaluator."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'GenericAgent-main'))
sys.path.insert(0, str(HERE / 'vendor'))

import llmcore
from .episode import PoSEpisode, execution_config
from .worker import RoleTransport


def safe_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write('\n')


class PublicLogger:
    def __init__(self, path):
        self.path = path
        self.stream = path.open('x', encoding='utf-8', newline='\n')
    def log(self, event, **data):
        # Transport exception text can contain a private endpoint. The type,
        # role, stage and attempted HTTP status remain sufficient here.
        data.pop('error', None)
        self.stream.write(json.dumps({'event': event, **data},
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
                except (ValueError, AttributeError):
                    pass
            yield line
    def json(self):
        value = self.response.json()
        if isinstance(value, dict) and value.get('model'):
            self.row['returned_model'] = value['model']
        return value


def exhaust(generator):
    try:
        while True:
            next(generator)
    except StopIteration as stopped:
        return stopped.value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-file', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=False)
    profile_path = args.profile_file.resolve(strict=True)
    profile = runpy.run_path(str(profile_path))['native_claude_cc_vibe_opus48']
    if profile.get('model') != 'claude-opus-4-8':
        raise RuntimeError('frozen Task model differs')
    safe_json(root / 'identity.json', {'schema': 'pos-ga-live-compatibility-v1',
        'profile_sha256': hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        'model_requested': profile['model'], 'task_tools_executed': 0,
        'official_evaluator_calls': 0})
    logger = PublicLogger(root / 'role_events.jsonl')
    wire = []
    phase = {'name': 'task_step_1'}
    original_post = llmcore.requests.post
    def post(url, **kwargs):
        row = {'phase': phase['name'], 'attempt': len(wire) + 1,
               'model_visible_payload': {k: v for k, v in kwargs['json'].items()
                                         if k != 'metadata'},
               'http_status': None, 'returned_model': None}
        wire.append(row)
        try:
            response = original_post(url, **kwargs)
            row['http_status'] = response.status_code
            return ResponseTap(response, row)
        except BaseException as error:
            row['error_type'] = type(error).__name__
            raise
    llmcore.requests.post = post
    report = {'schema': 'pos-ga-live-compatibility-result-v1',
              'status': 'failed', 'phase': phase['name'],
              'task_logical_calls': 0, 'pos_logical_calls': 0,
              'task_tools_executed': 0, 'official_evaluator_calls': 0,
              'public_task_responses': []}
    transport = None
    try:
        task = llmcore.NativeClaudeSession(profile)
        task.system = ('Synthetic protocol check only. For the first request, use the '
            'native tool probe with an empty object. No actual tool will run. '
            'Treat later observations as explicitly synthetic.')
        task.tools = [{'type': 'function', 'function': {'name': 'probe',
            'description': 'Synthetic no-op protocol marker; never executed.',
            'parameters': {'type': 'object', 'properties': {}}}}]
        first = {'role': 'user', 'content': [{'type': 'text', 'text':
            'SYNTHETIC_PROTOCOL_INPUT: request the native probe tool once.'}]}
        report['task_logical_calls'] += 1
        answer = exhaust(task.ask_stateless(first))
        report['public_task_responses'].append({'step': 1,
            'content': answer.content, 'hidden_thinking_present': bool(answer.thinking),
            'tools': [{'id': call.id, 'name': call.function.name,
                       'arguments': call.function.arguments} for call in answer.tool_calls]})
        if (answer.content.startswith('!!!Error:') or
                not any(call.function.name == 'probe' for call in answer.tool_calls)):
            raise RuntimeError('native synthetic tool call not parsed')
        phase['name'] = 'task_step_2'
        second = {'role': 'user', 'content': [{'type': 'text', 'text':
            'SYNTHETIC_PUBLIC_OBSERVATION: probe was NOT executed. This is a '
            'provided test observation, not a native tool_result. Continue with '
            'a short public acknowledgement; do not infer external success.'}]}
        report['task_logical_calls'] += 1
        answer = exhaust(task.ask_stateless(second))
        report['public_task_responses'].append({'step': 2,
            'content': answer.content, 'hidden_thinking_present': bool(answer.thinking),
            'tools': [{'id': call.id, 'name': call.function.name,
                       'arguments': call.function.arguments} for call in answer.tool_calls]})
        if answer.content.startswith('!!!Error:'):
            raise RuntimeError('second native synthetic response failed')
        phase['name'] = 'pos_reset_update'
        transport = RoleTransport(mode='profile', profile=profile, archive=logger)
        episode = PoSEpisode(case_id='synthetic-compatibility',
            config=execution_config(), logger=logger,
            belief_call=transport.caller('belief'),
            consistency_call=transport.caller('consistency'),
            progress_call=transport.caller('progress'))
        episode.reset(task='SYNTHETIC GOAL: inspect a marked item once.',
            observation='SYNTHETIC INITIAL OBSERVATION: item state unknown.',
            actions=task.tools)
        episode.update(thought='Synthetic inspection decision.',
            action_batch=[{'id': 'synthetic-action-1', 'name': 'probe',
                           'arguments': {}, 'order': 0,
                           'status': 'synthetic_observation_only'}],
            observation='SYNTHETIC PUBLIC OBSERVATION: marker is visible; '
                        'no real environment action occurred.', done=False)
        report['pos_logical_calls'] = len(transport.calls)
        report['pos_roles'] = [row['role'] for row in transport.calls]
        report['pos_result'] = episode.get_result()
        if not {'belief', 'consistency', 'progress'} <= set(report['pos_roles']):
            raise RuntimeError('released PoS role path incomplete')
        report['status'] = 'passed'
    except BaseException as error:
        report['phase'] = phase['name']
        report['error_type'] = type(error).__name__
    finally:
        if transport is not None:
            report['pos_logical_calls'] = len(transport.calls)
            report['pos_roles'] = [row['role'] for row in transport.calls]
        report['http_attempts'] = len(wire)
        report['returned_models'] = [row.get('returned_model') for row in wire]
        safe_json(root / 'http_attempts.json', wire)
        safe_json(root / 'result.json', report)
        logger.close()
        llmcore.requests.post = original_post
    print(json.dumps({'status': report['status'], 'phase': report['phase'],
        'task_logical_calls': report['task_logical_calls'],
        'pos_logical_calls': report['pos_logical_calls'],
        'http_attempts': report['http_attempts'],
        'error_type': report.get('error_type')}, ensure_ascii=False))
    if report['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
