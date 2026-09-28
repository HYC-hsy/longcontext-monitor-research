"""No model: actual bundle utility + fresh child native worker; synthetic budgets."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import socket

import pytest
from prepare_bundle import prepare, LIMITS, blob, POLICY_COMMIT, POLICY_PATH, M1, TASK, load_frozen_roadmap_runner, bind_roadmap_builder
from resource_budget import ResourceBudget, BudgetStop

HERE = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def deny_parent_network(monkeypatch):
    import requests
    calls = {'external_http_attempts': 0, 'socket_attempts': 0}
    def deny_http(*args, **kwargs):
        calls['external_http_attempts'] += 1
        raise AssertionError('parent HTTP denied')
    def deny_socket(*args, **kwargs):
        calls['socket_attempts'] += 1
        raise AssertionError('parent socket denied')
    monkeypatch.setattr(requests.sessions.Session, 'request', deny_http)
    monkeypatch.setattr(socket.socket, 'connect', deny_socket)
    monkeypatch.setattr(socket.socket, 'connect_ex', deny_socket)
    monkeypatch.setattr(socket, 'create_connection', deny_socket)
    yield calls
    assert calls == {'external_http_attempts': 0, 'socket_attempts': 0}


def test_explicit_source_does_not_fallback(tmp_path):
    with pytest.raises(FileNotFoundError): prepare(tmp_path / 'out', tmp_path / 'missing', False)
    from prepare_bundle import ROOT
    with pytest.raises(RuntimeError, match='not M1'): prepare(tmp_path / 'out', ROOT, False)
    assert not (tmp_path / 'out').exists()


def test_bundle_worker_identity_parity_and_failures():
    source = os.environ.get('M1_FROZEN_SOURCE')
    assert source, 'M1_FROZEN_SOURCE must be explicit; never fall back to current checkout'
    published = HERE / 'offline_receipts'
    published.mkdir(exist_ok=True)
    traces = []
    with tempfile.TemporaryDirectory(prefix='pilot-launch-check-') as temp:
        parent = Path(temp)
        runner, launch_imports = load_frozen_roadmap_runner(parent / 'launch-source')
        (parent / 'runtime-placeholder').mkdir()
        for index, enabled in enumerate((False, True)):
            root = parent / str(index)
            original_builder = bind_roadmap_builder(runner, supervisor_source=source,
                policy=enabled, budget_root=parent / 'panel-resources', record_id='engineering-fixture')
            copied, compose = runner.build_bundle(root, Path(source) / 'GenericAgent-main',
                parent / 'runtime-placeholder', 'UNVERIFIED_PYTHON_HOME',
                'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', 15340)
            runner.build_bundle = original_builder; runner._pilot_builder_bound = False
            output = published / ('candidate.json' if enabled else 'baseline.json')
            subprocess.run([sys.executable, '-I', str(HERE / 'capture_worker.py'),
                '--bundle', str(root), '--output', str(output)], check=True)
            trace = json.loads(output.read_text())
            binding = json.loads((copied / 'pilot_binding.json').read_text())
            identity = json.loads((root / 'isolation_identity.json').read_text())
            topology = json.loads(compose.read_text())
            assert binding['monitor_commit'] == M1 and binding['task_commit'] == TASK
            assert binding['preparation_only'] and not binding['execution_authorized']
            assert topology['services']['main']['network_mode'] == 'none'
            assert topology['services']['main']['environment']['GA_MONITOR_DCEC'] == '1'
            assert len(trace['requests']) == 3 and trace['actual_model_requests'] == 0
            assert trace['budget']['records']['engineering-fixture']['calls']['monitor'] == 3
            assert trace['budget']['records']['engineering-fixture']['attempts'] == 4
            assert trace['budget']['records']['engineering-fixture']['calls']['task'] == 1
            assert len(trace['task_transport_requests']) == 1
            assert not trace['budget']['records']['engineering-fixture']['blocked']
            assert not (copied / 'monitor_agent_core/dcec_control_slot.py').exists()
            # Frozen package takes precedence before GA bridge/runtime imports.
            assert all('/monitor_agent_core/' in p.replace('\\', '/') for p in trace['modules'].values())
            trace['mechanical_bundle_root'] = str(root)
            trace['binding'] = binding
            trace['launch_imports'] = launch_imports
            trace['isolation_identity'] = identity
            trace['compose'] = topology
            output.write_text(json.dumps(trace, indent=2), encoding='utf-8')
            traces.append(trace)
            # Missing/wrong frozen policy or frozen source bytes fail before transport.
            if enabled:
                (copied / 'pilot_policy.txt').write_text('not the frozen policy')
            else:
                with (copied / 'monitor_agent_core/agent.py').open('a') as f: f.write('\n# corrupted\n')
            failure = subprocess.run([sys.executable, '-I', '-c',
                "import sys; sys.path.insert(0, sys.argv[1]); import pilot_bootstrap; pilot_bootstrap.install(sys.argv[1])",
                str(copied)], capture_output=True, text=True)
            assert failure.returncode != 0
            (published / ('policy_failure.txt' if enabled else 'source_failure.txt')).write_text(failure.stderr, encoding='utf-8')
        body = blob(POLICY_COMMIT, POLICY_PATH).decode().strip()
        assert traces[0]['task_transport_requests'][0]['payload'] == traces[1]['task_transport_requests'][0]['payload']
        comparisons = []
        for a, b in zip(traces[0]['requests'], traces[1]['requests']):
            x, y = copy.deepcopy(a['payload']), copy.deepcopy(b['payload'])
            assert y['system'].count(body) == 1 and body not in x['system']
            y['system'] = y['system'].replace('\n\n' + body, '', 1)
            # Only explicitly recorded full bundle-root identities are normalized.
            def normalize(value, root):
                if isinstance(value, str):
                    return value.replace(root, '<bundle>').replace(json.dumps(root)[1:-1], '<bundle>')
                if isinstance(value, list): return [normalize(v, root) for v in value]
                if isinstance(value, dict): return {k: normalize(v, root) for k, v in value.items()}
                return value
            assert normalize(x, traces[0]['mechanical_bundle_root']) == normalize(y, traces[1]['mechanical_bundle_root'])
            comparisons.append({'allowed_strategy_occurrences': 1, 'remaining_full_payload_equal': True})
        (published / 'parity.json').write_text(json.dumps(dict(comparisons=comparisons,
            normalization='exact recorded full bundle roots only; raw payload retained',
            linux_container_started=False, actual_model_requests=0), indent=2), encoding='utf-8')


def test_budget_unified_purposes_retries_cache_unknown_and_limits(tmp_path):
    limits = dict(LIMITS, monitor_calls=3, task_calls=2, panel_calls=5)
    a = ResourceBudget(tmp_path / 'audit.json', 'one', limits)
    for purpose in ('review', 'continuation', 'format_repair'):
        ident = a.begin('monitor', purpose, 'review-1', 100, 10)
        a.attempt(ident)
        a.usage(ident, dict(input_tokens=2, output_tokens=1, cache_read_input_tokens=3, cache_creation_input_tokens=4))
        a.finish(ident)
    with pytest.raises(BudgetStop): a.begin('monitor', 'review', 'review-2', 100, 10)
    d = json.loads((tmp_path / 'audit.json').read_text())
    assert d['records']['one']['calls']['monitor'] == 3
    assert d['records']['one']['input'] == 27
    assert d['records']['one']['cache_read'] == 9
    assert d['records']['one']['cache_write'] == 12
    b = ResourceBudget(tmp_path / 'audit.json', 'two', limits)
    ident = b.begin('task', 'task', None, 100, 10)
    for _ in range(2):
        b.attempt(ident)
        b.usage(ident, dict(input_tokens=2, output_tokens=1))
    b.attempt(ident)  # Third sent attempt has no usage; panel pauses.
    with pytest.raises(BudgetStop): b.attempt(ident)
    b.finish(ident, 'synthetic_transport_failure')
    with pytest.raises(BudgetStop): b.begin('task', 'task', None, 100, 10)
    d = json.loads((tmp_path / 'audit.json').read_text())
    assert d['records']['two']['attempts'] == 3
    assert d['records']['two']['calls']['task'] == 1
    assert d['records']['two']['blocked']
    assert not d['monetary_limit_enforced']
    (HERE / 'offline_receipts/budget_synthetic.json').write_text(json.dumps(d, indent=2), encoding='utf-8')


def test_budget_inflight_reservation_and_delayed_overage(tmp_path):
    limits = dict(LIMITS, attempts_per_call=1, record_input=100, record_output=10, panel_input=100, panel_output=10)
    a = ResourceBudget(tmp_path / 'ledger.json', 'one', limits)
    first = a.begin('task', 'task', None, 80, 8)
    with pytest.raises(BudgetStop): a.begin('monitor', 'review', 'r', 80, 8)
    a.attempt(first); a.usage(first, dict(input_tokens=110, output_tokens=11)); a.finish(first)
    with pytest.raises(BudgetStop): a.begin('monitor', 'review', 'r', 1, 1)
    d = json.loads((tmp_path / 'ledger.json').read_text())
    assert any(e.get('exceeded_after_receipt') for e in d['events'])
    assert not d['pending']


def test_monitor_request_wrapper_purposes_and_no_extra_calls(tmp_path):
    from pilot_bootstrap import install_monitor_budget
    class FakeClient:
        context_window, max_tokens, review_id = 100, 10, 'r'
        def _request(self, tools): return self._request_once(tools)
        def _request_once(self, tools): return [], dict(input_tokens=1, output_tokens=1)
    client = FakeClient()
    ledger = ResourceBudget(tmp_path / 'audit.json', 'one', dict(LIMITS, monitor_calls=3))
    install_monitor_budget(client, ledger)
    for purpose in ('review', 'continuation', 'format_repair'):
        client.request_purpose = purpose; client._request([])
    with pytest.raises(BudgetStop): client._request([])
    d = json.loads((tmp_path / 'audit.json').read_text())
    assert d['records']['one']['calls']['monitor'] == 3
    assert d['records']['one']['attempts'] == 3


@pytest.mark.parametrize('cap_key', ['record_input', 'panel_input', 'record_output', 'panel_output'])
def test_retry_envelope_denied_before_send(tmp_path, cap_key):
    limits = dict(LIMITS, **{cap_key: 100})
    ledger = ResourceBudget(tmp_path / 'audit.json', 'A', limits)
    # The audited 80-token counterexample: even the first send is not admitted
    # when three permitted attempts would reserve 240 against a 100 cap.
    with pytest.raises(BudgetStop, match='reservation_limit'):
        ledger.begin('task', 'task', None, 80, 80)
    d = json.loads(ledger.path.read_text())
    assert d['panel_calls'] == 0 and d['records']['A']['attempts'] == 0
    assert not d['pending']


def test_known_retries_have_one_logical_call_and_full_envelope(tmp_path):
    limits = dict(LIMITS, record_input=240, panel_input=240)
    ledger = ResourceBudget(tmp_path / 'audit.json', 'A', limits)
    ident = ledger.begin('task', 'task', None, 80, 2)
    for _ in range(3):
        ledger.attempt(ident)
        ledger.usage(ident, {'input_tokens': 80, 'output_tokens': 2})
    with pytest.raises(BudgetStop, match='attempt_limit'): ledger.attempt(ident)
    assert not ledger.finish(ident)
    d = json.loads(ledger.path.read_text())
    assert d['panel_input'] == 240 and d['panel_calls'] == 1
    assert d['records']['A']['attempts'] == 3
    assert d['finished'][ident]['input_reserve'] == 240
    (HERE / 'offline_receipts/retry_envelope.json').write_text(json.dumps(d, indent=2), encoding='utf-8')


def test_unknown_sent_usage_preserves_envelope_and_pauses_other_record(tmp_path):
    limits = dict(LIMITS, attempts_per_call=1, record_input=100, panel_input=100)
    a = ResourceBudget(tmp_path / 'audit.json', 'A', limits)
    b = ResourceBudget(a.path, 'B', limits)
    ident = a.begin('task', 'task', None, 80, 2)
    a.attempt(ident)
    assert a.finish(ident, 'synthetic_transport_failure')
    with pytest.raises(BudgetStop, match='panel_resource_paused'):
        b.begin('task', 'task', None, 100, 2)
    d = json.loads(a.path.read_text())
    assert d['panel_input'] == 0 and d['panel_paused']
    assert d['unresolved'][ident]['input_reserve'] == 80
    assert d['finished'][ident]['error_type'] == 'synthetic_transport_failure'
    assert d['records']['B']['attempts'] == 0
    (HERE / 'offline_receipts/unknown_usage_pause.json').write_text(json.dumps(d, indent=2), encoding='utf-8')


def test_partial_usage_keeps_known_buckets(tmp_path):
    ledger = ResourceBudget(tmp_path / 'partial.json', 'A', LIMITS)
    ident = ledger.begin('task', 'task', None, 80, 8)
    ledger.attempt(ident)
    ledger.usage(ident, {'input_tokens': 12, 'cache_read_input_tokens': 5})
    assert ledger.finish(ident, 'synthetic_incomplete_usage')
    d = json.loads(ledger.path.read_text())
    assert d['panel_input'] == 17 and d['panel_output'] == 0
    assert d['panel_paused'] and ident in d['unresolved']
    assert d['finished'][ident]['usage_records'][0]['output_tokens'] is None


def test_unknown_retry_and_reservation_breach_stop_pending_sends(tmp_path):
    a = ResourceBudget(tmp_path / 'unknown.json', 'A', LIMITS)
    ident = a.begin('task', 'task', None, 20, 2)
    a.attempt(ident)
    with pytest.raises(BudgetStop, match='panel_resource_paused'): a.attempt(ident)
    assert a.finish(ident, 'synthetic_transport_failure')
    a = ResourceBudget(tmp_path / 'breach.json', 'A', LIMITS)
    b = ResourceBudget(a.path, 'B', LIMITS)
    first = a.begin('task', 'task', None, 20, 2)
    other = b.begin('monitor', 'review', 'r', 20, 2)
    a.attempt(first)
    a.usage(first, {'input_tokens': 30, 'output_tokens': 3, 'test_marker': 'original synthetic receipt'})
    with pytest.raises(BudgetStop, match='panel_resource_paused'): a.attempt(first)
    with pytest.raises(BudgetStop, match='panel_resource_paused'): b.attempt(other)
    assert a.finish(first) and b.finish(other)
    with pytest.raises(BudgetStop, match='panel_resource_paused'):
        b.begin('task', 'task', None, 1, 1)
    d = json.loads(a.path.read_text())
    assert d['panel_input'] == 30 and d['panel_output'] == 3
    assert not d.get('unresolved')  # B never sent; no unknown billable use.
    assert d['finished'][first]['reservation_breached']
    assert any(e.get('raw_usage', {}).get('test_marker') for e in d['events'])
    (HERE / 'offline_receipts/reservation_breach.json').write_text(json.dumps(d, indent=2), encoding='utf-8')


def test_task_stream_delivery_precedes_final_budget_stop(tmp_path, monkeypatch):
    # Exercise the real experimental wrapper with a synthetic streaming base.
    # No claim that settlement can retract content already yielded upstream.
    import types
    import requests
    import pilot_bootstrap
    delivered = []
    class Session:
        model, context_win, max_tokens = 'claude-opus-4-8', 20, 2
        def raw_ask(self, messages):
            requests.post('fake://transport')
            yield 'already delivered synthetic content'
            fake._record_usage({'input_tokens': 30, 'output_tokens': 3}, 'messages')
    fake = types.SimpleNamespace(NativeClaudeSession=Session, _record_usage=lambda value, mode: None)
    monkeypatch.setitem(sys.modules, 'llmcore', fake)
    monkeypatch.setattr(pilot_bootstrap, 'install', lambda root: None)
    monkeypatch.setattr(requests, 'post', lambda *args, **kwargs: None)
    (tmp_path / 'pilot_binding.json').write_text(json.dumps({'budget_limits': LIMITS}))
    monkeypatch.setenv('PILOT_BUDGET_PATH', str(tmp_path / 'audit.json'))
    monkeypatch.setenv('PILOT_RECORD_ID', 'stream')
    pilot_bootstrap.install_task(tmp_path)
    stream = Session().raw_ask([])
    delivered.append(next(stream))
    with pytest.raises(BudgetStop): next(stream)
    d = json.loads((tmp_path / 'audit.json').read_text())
    assert delivered == ['already delivered synthetic content']
    assert d['panel_paused'] and d['panel_input'] == 30
    (HERE / 'offline_receipts/stream_stop_order.json').write_text(json.dumps({
        'synthetic_stream_content_delivered_before_stop': delivered,
        'ledger': d, 'coverage': 'experimental Task wrapper; not full Task control loop'}, indent=2), encoding='utf-8')


def test_monitor_settlement_stops_completed_return_not_response_evidence(tmp_path):
    from pilot_bootstrap import install_monitor_budget
    class FakeClient:
        context_window, max_tokens, review_id = 20, 2, 'r'
        request_purpose = 'review'
        responses = []
        def _request(self, tools): return self._request_once(tools)
        def _request_once(self, tools):
            result = ([{'type': 'text', 'text': 'synthetic retained response'}],
                      {'input_tokens': 30, 'output_tokens': 3})
            self.responses.append(result)
            return result
    client = FakeClient()
    ledger = ResourceBudget(tmp_path / 'audit.json', 'monitor', LIMITS)
    install_monitor_budget(client, ledger)
    returned = []
    with pytest.raises(BudgetStop): returned.append(client._request([]))
    assert not returned and len(client.responses) == 1
    d = json.loads(ledger.path.read_text())
    assert d['panel_paused'] and d['panel_input'] == 30
    (HERE / 'offline_receipts/monitor_stop_order.json').write_text(json.dumps({
        'synthetic_received_response': client.responses,
        'caller_completed_results': returned, 'ledger': d}, indent=2), encoding='utf-8')
