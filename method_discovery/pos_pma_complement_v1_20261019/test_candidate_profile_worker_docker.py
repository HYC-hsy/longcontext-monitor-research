"""Deployed candidate worker/profile-spool check; all responses are scripted.

This is not a live provider compatibility test or a Harbor Task run.
"""
from __future__ import annotations

import asyncio
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
POS = ROOT / 'method_discovery/pos_upstream_ga_v1_20261017'
PMA = ROOT / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
HERE = Path(__file__).resolve().parent
RUNTIME = Path('E:/LongContext/bench_runtime/m2/linux')
IMAGE = 'alexgshaw/db-wal-recovery:20251031'
RUN_ID, TASK_ID = 'candidate-profile-zero-model', 'synthetic-protocol'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def container_main():
    source, archive = Path('/opt/genericagent'), Path('/run/pos-archive')
    pos = source / 'pos_runtime'
    initial = {'goal_specification': 'Observe a service.', 'entities': [],
        'states': [], 'relations': [], 'epistemic_gaps': [],
        'achievement_gaps': [{'target': 'service available', 'reason': 'not observed'}],
        'frontier': {'gap_type': 'achievement', 'target': 'service available'}}
    delta = {'remove_state_ids': [], 'remove_relation_ids': [],
        'upsert_entities': [], 'upsert_states': [], 'upsert_relations': [],
        'epistemic_gaps': [], 'achievement_gaps': initial['achievement_gaps'],
        'frontier': initial['frontier']}
    scripted = [json.dumps(value) for value in (initial, {'issues': []},
        delta, {'issues': []}, {'progress': 0, 'score': 0.0,
        'affected_record_ids': [], 'reason': 'No change observed.'})]
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            received.append({'stream': payload.get('stream'),
                'max_tokens': payload.get('max_tokens'),
                'thinking': payload.get('thinking'),
                'temperature': payload.get('temperature')})
            answer = scripted.pop(0)
            events = [
                {'type': 'message_start', 'message': {'usage': {'input_tokens': 2}}},
                {'type': 'content_block_start', 'content_block': {'type': 'text', 'text': ''}},
                {'type': 'content_block_delta', 'delta': {'type': 'text_delta', 'text': answer}},
                {'type': 'content_block_stop'},
                {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'},
                 'usage': {'output_tokens': 3}}, {'type': 'message_stop'}]
            data = ''.join('data: ' + json.dumps(row) + '\n\n' for row in events).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    profile = archive / 'fake_profile.json'
    profile.write_text(json.dumps({'fixture': {
        'apibase': f'http://127.0.0.1:{server.server_port}',
        'apikey': 'sk-ant-SYNTHETIC-NOT-SECRET', 'model': 'claude-opus-4-8',
        'max_tokens': 4096, 'thinking_type': 'adaptive', 'temperature': 1,
        'max_retries': 0, 'stream': True}}), encoding='utf-8')
    vendor = pos / 'vendor'
    pma_vendor = pos / 'pma_vendor'
    binding = {'schema': 'pos-ga-transport-binding-v1', 'transport': 'profile',
        'run_id': RUN_ID, 'task_id': TASK_ID,
        'upstream_commit': '6818cfa6434dbc91fcf67f0b3eb12a91db47433f',
        'manifest_sha256': '1' * 64, 'authorization_sha256': '2' * 64,
        'config_sha256': '3' * 64,
        'worker_sha256': digest(pos / 'worker.py'),
        'episode_sha256': digest(pos / 'episode.py'),
        'citation_fix_sha256': digest(pos / 'citation_fix.py'),
        'candidate_sha256': digest(pos / 'candidate.py'),
        'memory_adapter_sha256': digest(pos / 'memory_adapter.py'),
        'event_spool_sha256': digest(pos / 'event_spool.py'),
        'profile_sha256': digest(profile),
        'vendor_files_sha256': {p.relative_to(vendor).as_posix(): digest(p)
            for p in vendor.rglob('*') if p.is_file()},
        'pma_vendor_files_sha256': {p.relative_to(pma_vendor).as_posix(): digest(p)
            for p in pma_vendor.rglob('*') if p.is_file()},
        'candidate_config': {'pma_trigger': {'interval': 1, 'first_step': True,
            'sliding_window_size': 8, 'actor_step_mapping': 'actor_attempt_plus_one'},
            'candidate_limits': {'task_panel_chars': 16000,
                'phase2_advisory_chars': 16000, 'revision_chars': 12000,
                'history_events': 4, 'history_event_chars': 2000,
                'related_records': 8, 'complete_request_bytes': 90000,
                'byte_budget_basis': 'conservative_engineering_cap_not_token_context',
                'output_reserve': 'existing_frozen_max_tokens_per_role'},
            'pma_profile_sha256': '4' * 64}}
    bound = archive / 'binding.json'
    bound.write_text(json.dumps(binding), encoding='utf-8')
    sys.path.insert(0, str(source))
    from pos_bridge import PoSBridge
    deadline = time.time() + 90
    os.environ.update(GA_PMA_CAPTURE_TASK_REQUESTS='1', GA_POS_TIMEOUT='20',
        GA_POS_DEADLINE_EPOCH=str(deadline), PYTHONDONTWRITEBYTECODE='1')
    bridge = PoSBridge(worker_script=pos / 'worker.py', vendor=vendor,
        episode_module=pos / 'episode.py', archive=archive / 'events.jsonl',
        mode='profile', profile_file=profile, profile_name='fixture',
        run_id=RUN_ID, task_id=TASK_ID, binding_file=bound,
        timeout=20, deadline_epoch=deadline)
    try:
        reset = bridge.exchange('reset', case_id=TASK_ID, task='Observe a service.',
            observation='Not yet observed.', actions=[], candidate=True)
        panel = bridge.exchange('decision_panel', observation='Not yet observed.')
        bridge.exchange('request_accepted', panel=panel, event_id='synthetic-sent-1')
        updated = bridge.exchange('update', actor_attempt=1, transition_id='batch-1',
            thought='Inspect', action_batch=[{'id': 'call-1', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation='Still not observed.', source_events=[{'tool_use_id': 'call-1',
                'result': {'stdout': 'Still not observed.'}}], done=False)
        finish = bridge.exchange('finish', reason='synthetic_end',
            observation='Still not observed.')
    finally:
        bridge.close()
        server.shutdown()
    assert bridge.process.returncode == 0, bridge.process.returncode
    assert len(received) == 5 and not scripted, received
    assert all(item['stream'] is True and item['thinking'] == {'type': 'disabled'}
               and item['temperature'] == 0 for item in received)
    assert reset['panel'] and panel['included_advice'] == 'Synthetic PMA advice.'
    assert updated['latest_actor_transition'] == 'batch-1'
    assert finish['status']
    rows = [json.loads(line) for line in (archive / 'events.jsonl').read_text().splitlines()]
    assert sum(row['event'] == 'candidate_pma_request' for row in rows) == 4
    print(json.dumps({'status': 'pass', 'mode': 'profile', 'fake_http_pos_roles':
        len(received), 'host_fake_pma_roles': 4,
        'worker_exit': bridge.process.returncode,
        'pma_request_rows': 4, 'candidate_panel_advice_delivered': True}))


def host_main():
    from long_context_bench.scripts.isolated_run_bundle import build_bundle
    for path in (PMA / 'vendor/pma_89e5c0d/external/harbor/src',
                 PMA / 'vendor/pma_89e5c0d/src', PMA):
        sys.path.insert(0, str(path))
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.candidate_transport_worker import TransportEpisode
    from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.event_spool import EventDispatcher
    root = Path(os.environ['CANDIDATE_PROFILE_TEST_ROOT']).resolve()
    root.mkdir(parents=True, exist_ok=False)
    stage = root / 'stage'
    stage.mkdir()
    for path in (ROOT / 'GenericAgent-main').glob('*.py'):
        if path.name != 'mykey.py': shutil.copy2(path, stage / path.name)
    (stage / 'mykey.py').write_text("native_claude_cc_vibe_opus48 = {'apibase': "
        "'https://fake.invalid', 'apikey': 'SYNTHETIC', "
        "'model': 'claude-opus-4-8', 'stream': True}\n", encoding='utf-8')
    pos = stage / 'pos_runtime'
    pos.mkdir()
    for name in ('worker.py', 'episode.py', 'citation_fix.py'):
        shutil.copy2(POS / name, pos / name)
    for name in ('candidate.py', 'memory_adapter.py'):
        shutil.copy2(HERE / name, pos / name)
    shutil.copy2(PMA / 'event_spool.py', pos / 'event_spool.py')
    shutil.copytree(POS / 'vendor', pos / 'vendor',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(PMA / 'vendor/pma_89e5c0d/src', pos / 'pma_vendor/src',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    source, _ = build_bundle(root / 'bundle', stage, RUNTIME, '/opt/m2-runtime',
                             'native_claude_cc_vibe_opus48', None, 15340)
    archive = root / 'control/pos_archive'
    archive.mkdir(parents=True)
    spool = root / 'control/spool'
    requests, responses = spool / 'requests', spool / 'responses'
    requests.mkdir(parents=True)
    responses.mkdir()
    private = root / 'host_private'
    private.mkdir()
    class FakeLLM:
        def __init__(self): self.calls = 0
        async def call(self, **kwargs):
            self.calls += 1
            if kwargs['tools'] is not None:
                return SimpleNamespace(content='', tool_calls=[])
            content = ('<context_for_action>Synthetic PMA advice.</context_for_action>'
                       if self.calls == 2 else '<no_intervention/>')
            return SimpleNamespace(content=content, tool_calls=[])
    fake = FakeLLM()
    episode = TransportEpisode(fake, run_id=RUN_ID, task_id=TASK_ID, archive=private)
    dispatcher = EventDispatcher(episode, requests, responses, deadline_epoch=time.time()+120)
    stop = threading.Event()
    errors = []
    def dispatch():
        while not stop.is_set():
            try: asyncio.run(dispatcher.serve_once())
            except BaseException as error: errors.append(type(error).__name__); break
            time.sleep(.01)
    thread = threading.Thread(target=dispatch, daemon=True)
    thread.start()
    command = ['docker', 'run', '--rm', '--network', 'none',
        '--mount', f'type=bind,source={source},target=/opt/genericagent,readonly',
        '--mount', f'type=bind,source={archive},target=/run/pos-archive',
        '--mount', f'type=bind,source={requests},target=/run/pma-bridge/requests',
        '--mount', f'type=bind,source={responses},target=/run/pma-bridge/responses',
        '--mount', f'type=bind,source={RUNTIME},target=/opt/m2-runtime,readonly',
        '--mount', f'type=bind,source={ROOT},target=/opt/research,readonly',
        '-e', 'PYTHONPATH=/opt/research', IMAGE,
        '/opt/m2-runtime/ga-env/bin/python', '-B',
        '/opt/research/method_discovery/pos_pma_complement_v1_20261019/test_candidate_profile_worker_docker.py',
        '--in-container']
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
    finally:
        stop.set()
        thread.join(timeout=5)
    (root / 'docker.stdout.txt').write_text(completed.stdout, encoding='utf-8')
    (root / 'docker.stderr.txt').write_text(completed.stderr, encoding='utf-8')
    assert completed.returncode == 0, (completed.returncode, completed.stderr[-3000:])
    assert fake.calls == 4 and not errors, (fake.calls, errors)
    print(completed.stdout)


if __name__ == '__main__':
    if '--in-container' in sys.argv: container_main()
    else: host_main()
