"""No-model Docker check of the deployed PoS worker's streaming HTTP path."""
from __future__ import annotations

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
import unittest

HERE = Path(__file__).resolve().parent
CHECKOUT = HERE.parents[1]
RUNTIME = Path('E:/LongContext/bench_runtime/m2/linux')
IMAGE = 'alexgshaw/db-wal-recovery:20251031'
RUN_ID = 'pos-profile-sse-zero-model'
TASK_ID = 'synthetic-worker-protocol'
FAKE_KEY = 'sk-ant-FAKE-ONLY-NOT-A-PROVIDER-SECRET'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture_replies():
    initial = {'goal_specification': 'Mug must be clean.',
        'entities': [{'entity_id':'e1','entity_type':'mug','name':'mug'}],
        'states': [{'state_id':'s1','entity_id':'e1','description':'Mug dirty.',
                    'source_type':'observed','probability':1.0}],
        'relations': [], 'epistemic_gaps': [],
        'achievement_gaps': [{'target':'Mug clean','reason':'Currently dirty'}],
        'frontier': {'gap_type':'achievement','target':'Mug clean'}}
    delta = {'remove_state_ids': [], 'remove_relation_ids': [],
        'upsert_entities': [], 'upsert_states': [], 'upsert_relations': [],
        'epistemic_gaps': [], 'achievement_gaps': initial['achievement_gaps'],
        'frontier': initial['frontier']}
    return [json.dumps(value) for value in (
        initial, {'issues': []}, {'belief_text':'Mug dirty.'},
        delta, {'issues': []},
        {'progress':0,'score':0.0,'affected_record_ids':[],
         'reason':'No observed improvement.'},
        {'belief_text':'Mug dirty.'})]


def container_main():
    archive = Path('/run/pos-archive')
    source = Path('/opt/genericagent')
    worker = source / 'pos_runtime/worker.py'
    episode = source / 'pos_runtime/episode.py'
    vendor = source / 'pos_runtime/vendor'
    responses = fixture_replies()
    received = []
    stall_mode = {'on':False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            payload = json.loads(body)
            received.append({'path':self.path,'payload':payload,
                             'stream':payload.get('stream')})
            if len(received) >= 4 and not stall_mode['on']:
                time.sleep(0.9)  # four sequential update roles exceed 3s in total
            if not responses:
                self.send_error(500)
                return
            answer = responses.pop(0)
            events = [
                {'type':'message_start','message':{'usage':{'input_tokens':3}}},
                {'type':'content_block_start','content_block':{'type':'thinking','thinking':''}},
                {'type':'content_block_delta','delta':{'type':'thinking_delta',
                    'thinking':'HIDDEN_SYNTHETIC_THOUGHT_CANARY'}},
                {'type':'content_block_stop'},
                {'type':'content_block_start','content_block':{'type':'text','text':''}},
                {'type':'content_block_delta','delta':{'type':'text_delta','text':answer}},
                {'type':'content_block_stop'},
                {'type':'message_delta','delta':{'stop_reason':'end_turn'},
                 'usage':{'output_tokens':5}},
                {'type':'message_stop'},
            ]
            data = ''.join('data: '+json.dumps(row)+'\n\n' for row in events).encode()
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            if stall_mode['on']:
                time.sleep(4.0)  # exceeds the scaled 3s single-provider cap
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    profile = archive / 'fake_profile.json'
    profile.write_text(json.dumps({'fixture': {'apibase':f'http://127.0.0.1:{server.server_port}',
        'apikey':FAKE_KEY, 'model':'claude-opus-4-8', 'max_tokens':4096,
        'thinking_type':'adaptive', 'temperature':1, 'max_retries':0,
        'stream':True}}), encoding='utf-8')
    binding = archive / 'binding.json'
    vendor_hashes = {path.relative_to(vendor).as_posix(): digest(path)
                     for path in vendor.rglob('*') if path.is_file()}
    binding.write_text(json.dumps({'schema':'pos-ga-transport-binding-v1',
        'transport':'profile', 'run_id':RUN_ID,'task_id':TASK_ID,
        'upstream_commit':'6818cfa6434dbc91fcf67f0b3eb12a91db47433f',
        'manifest_sha256':'1'*64,'authorization_sha256':'2'*64,
        'config_sha256':'3'*64, 'worker_sha256':digest(worker),
        'episode_sha256':digest(episode), 'profile_sha256':digest(profile),
        'vendor_files_sha256':vendor_hashes}), encoding='utf-8')
    sys.path.insert(0, str(source))
    from pos_bridge import PoSBridge
    overall_deadline = time.time() + 60
    os.environ.update(GA_PMA_CAPTURE_TASK_REQUESTS='1', GA_POS_TIMEOUT='3',
                      GA_POS_DEADLINE_EPOCH=str(overall_deadline),
                      PYTHONDONTWRITEBYTECODE='1')
    bridge = PoSBridge(worker_script=worker, vendor=vendor,
        episode_module=episode, archive=archive/'events.jsonl', mode='profile',
        profile_file=profile, profile_name='fixture', run_id=RUN_ID,
        task_id=TASK_ID, binding_file=binding, timeout=3,
        deadline_epoch=overall_deadline)
    commands = [
        {'kind':'reset','case_id':TASK_ID,'task':'Clean mug.',
         'observation':'Mug dirty.','actions':[]},
        {'kind':'update','thought':'Inspect','action_batch':[{'id':'c1',
         'name':'synthetic_inspect','arguments':{},'order':0,'status':'executed'}],
         'observation':'Still dirty.','done':False},
        {'kind':'finish','reason':'CURRENT_TASK_DONE','observation':'Still dirty.'},
    ]
    rows = []
    update_elapsed = None
    try:
        for row in commands:
            started = time.monotonic()
            rows.append(bridge.exchange(row.pop('kind'), **row))
            if 'action_batch' in row:
                update_elapsed = time.monotonic() - started
    finally:
        bridge.close()
    assert bridge.process.returncode == 0 and len(rows) == 3, (
        bridge.process.returncode, rows)
    assert update_elapsed > 3, update_elapsed
    assert len(received) == 7 and not responses, (len(received), responses)
    assert all(row['stream'] is True for row in received)
    assert [row['payload']['max_tokens'] for row in received] == [4096,512,4096,4096,512,512,4096]
    assert all(row['payload']['thinking'] == {'type':'disabled'} and
               row['payload']['temperature'] == 0 for row in received)
    from method_discovery.pos_upstream_ga_v1_20261017.provider_capture import inspect_provider_capture
    capture = inspect_provider_capture(archive,RUN_ID,TASK_ID,profile_mode=True)
    assert capture['capture_complete'] is True, capture
    provider = (archive/'events.provider.jsonl').read_text(encoding='utf-8')
    assert FAKE_KEY not in provider and 'HIDDEN_SYNTHETIC_THOUGHT_CANARY' not in provider
    assert f'127.0.0.1:{server.server_port}' not in provider
    from method_discovery.pos_upstream_ga_v1_20261017.collect_native_shared import collect_provider_capture
    collected = collect_provider_capture(archive,archive/'public_provider',
        [FAKE_KEY,f'http://127.0.0.1:{server.server_port}'],
        RUN_ID,TASK_ID,profile_mode=True)
    assert collected['capture']['capture_complete'] is True
    assert len(collected['files']) >= 3
    for row in collected['files']:
        public_bytes = (archive/'public_provider'/row['path']).read_bytes()
        assert hashlib.sha256(public_bytes).hexdigest() == row['public_sha256']
        assert FAKE_KEY.encode() not in public_bytes
        assert b'HIDDEN_SYNTHETIC_THOUGHT_CANARY' not in public_bytes
    diagnostics = [json.loads(line) for line in
                   (archive/'events.bridge.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [row['outcome'] for row in diagnostics if row['event']=='command_finished'] == [
        'receipt_ok'] * 3
    assert json.loads((archive/'events.close.json').read_text())['status'] == 'graceful_exit'
    timeout_archive = archive/'timeout_case'
    timeout_archive.mkdir()
    timeout_run = RUN_ID + '-timeout'
    timeout_binding = timeout_archive/'binding.json'
    bound = json.loads(binding.read_text(encoding='utf-8'))
    bound['run_id'] = timeout_run
    timeout_binding.write_text(json.dumps(bound), encoding='utf-8')
    responses.extend([fixture_replies()[0]] * 3)  # correction is allowed, not transport replay
    stall_mode['on'] = True
    timeout_bridge = PoSBridge(worker_script=worker, vendor=vendor,
        episode_module=episode, archive=timeout_archive/'events.jsonl',
        mode='profile', profile_file=profile, profile_name='fixture',
        run_id=timeout_run, task_id=TASK_ID, binding_file=timeout_binding,
        timeout=3, deadline_epoch=time.time()+30)
    try:
        try:
            timeout_bridge.exchange('reset', case_id=TASK_ID,
                task='Clean mug.', observation='Mug dirty.', actions=[])
        except Exception:
            pass  # original worker/parser failure is examined in the ledgers below
    finally:
        timeout_bridge.close()
    timeout_provider = [json.loads(line) for line in
        (timeout_archive/'events.provider.jsonl').read_text(encoding='utf-8').splitlines()]
    attempts_by_call = {}
    for item in timeout_provider:
        if item['event_type'] == 'provider_request_attempt':
            attempts_by_call[item['llm_call_id']] = (
                attempts_by_call.get(item['llm_call_id'], 0) + 1)
    assert attempts_by_call and max(attempts_by_call.values()) == 1, attempts_by_call
    assert any(item['event_type']=='provider_response' and
               item['payload'].get('outcome')=='transport_error' and
               item['payload'].get('error_type')=='Timeout'
               for item in timeout_provider), timeout_provider[-5:]
    timeout_diagnostics = [json.loads(line) for line in
        (timeout_archive/'events.bridge.jsonl').read_text().splitlines()]
    assert any(row['event']=='command_finished' and row['outcome']=='exception' and
               row['request_sent'] is True and row['result_unknown'] is False
               for row in timeout_diagnostics)
    assert any(row['event']=='bridge_closed' for row in timeout_diagnostics)
    server.shutdown()
    result = {'status':'pass','model_calls':0,'fake_http_requests':len(received),
              'worker_exit':bridge.process.returncode,'worker_receipts':rows,
              'update_elapsed_seconds':update_elapsed,
              'provider_timeout_seconds':3,'provider_capture':capture,
              'timeout_case_attempts_by_call':attempts_by_call,
              'collected_provider':collected,
              'source_sha256':{name:digest(source/name) for name in
                ('llmcore.py','research_runtime.py','pos_runtime/worker.py',
                 'pos_runtime/episode.py')}}
    (archive/'profile_integration_result.json').write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'pass','fake_http_requests':len(received),
                      'update_elapsed_seconds':update_elapsed,
                      'provider_capture':capture},ensure_ascii=False))


def host_main():
    sys.path.insert(0, str(CHECKOUT))
    from long_context_bench.scripts.isolated_run_bundle import build_bundle
    root = Path(os.environ['POS_PROFILE_TEST_ROOT']).resolve()
    root.mkdir(parents=True, exist_ok=False)
    stage = root/'stage'
    stage.mkdir()
    for path in (CHECKOUT/'GenericAgent-main').glob('*.py'):
        if path.name != 'mykey.py': shutil.copy2(path,stage/path.name)
    (stage/'mykey.py').write_text("native_claude_cc_vibe_opus48 = " + repr({
        'apibase':'https://fake.invalid','apikey':FAKE_KEY,
        'model':'claude-opus-4-8','stream':True})+'\n',encoding='utf-8')
    pos = stage/'pos_runtime'
    pos.mkdir()
    for name in ('worker.py','episode.py'):
        shutil.copy2(HERE/name,pos/name)
    shutil.copytree(HERE/'vendor',pos/'vendor',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    source,_ = build_bundle(root/'bundle',stage,RUNTIME,'/opt/m2-runtime',
                            'native_claude_cc_vibe_opus48',None,15340)
    archive = root/'control'/'pos_archive'
    archive.mkdir(parents=True)
    command = ['docker','run','--rm','--network','none',
        '--mount',f'type=bind,source={source},target=/opt/genericagent,readonly',
        '--mount',f'type=bind,source={archive},target=/run/pos-archive',
        '--mount',f'type=bind,source={RUNTIME},target=/opt/m2-runtime,readonly',
        '--mount',f'type=bind,source={CHECKOUT},target=/opt/research,readonly',
        '-e','PYTHONPATH=/opt/research',IMAGE,
        '/opt/m2-runtime/ga-env/bin/python','-B',
        '/opt/research/method_discovery/pos_upstream_ga_v1_20261017/test_profile_worker_integration.py',
        '--in-container']
    completed = subprocess.run(command,capture_output=True,text=True,timeout=180)
    (root/'docker.stdout.txt').write_text(completed.stdout,encoding='utf-8')
    (root/'docker.stderr.txt').write_text(completed.stderr,encoding='utf-8')
    assert completed.returncode == 0, (completed.stdout,completed.stderr)
    print(completed.stdout)


if __name__ == '__main__':
    if '--in-container' in sys.argv: container_main()
    else: host_main()
