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
    for _ in range(3): b.attempt(ident)
    with pytest.raises(BudgetStop): b.attempt(ident)
    b.usage(ident, dict(input_tokens=2, output_tokens=1))
    b.finish(ident, 'synthetic_transport_failure')
    with pytest.raises(BudgetStop): b.begin('task', 'task', None, 100, 10)
    d = json.loads((tmp_path / 'audit.json').read_text())
    assert d['records']['two']['attempts'] == 3
    assert d['records']['two']['calls']['task'] == 1
    assert d['records']['two']['blocked']
    assert not d['monetary_limit_enforced']
    (HERE / 'offline_receipts/budget_synthetic.json').write_text(json.dumps(d, indent=2), encoding='utf-8')


def test_budget_inflight_reservation_and_delayed_overage(tmp_path):
    limits = dict(LIMITS, record_input=100, record_output=10, panel_input=100, panel_output=10)
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
