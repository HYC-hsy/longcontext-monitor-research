"""Offline configuration and transport plumbing, not sampling-effect evidence."""
import asyncio
import copy
import json
import math

import pytest

from pma_model_profile import load_profile, read_context_temperature, READ_CONTEXT
from test_predictive_tool_recovery import block_network  # noqa: F401


def profile(**overrides):
    return dict(provider='anthropic', api_mode='messages', model='claude-opus-4-8',
        apibase='https://example.invalid', apikey='synthetic-only',
        thinking_type='adaptive', reasoning_effort='high', max_tokens=8192,
        read_timeout=300, max_retries=1, **overrides)


@pytest.mark.parametrize('temperature', [0, 0.2, 0.5, 1, 1.0])
def test_profile_accepts_only_requested_manager_temperature(temperature):
    p = profile(temperature=temperature)
    name, resolved = load_profile(json.dumps({'pma_model': p}).encode(), READ_CONTEXT)
    assert name == 'pma_model'
    assert resolved == p


def test_omitted_defaults_to_one_and_legacy_profile_is_untouched():
    p = profile()
    _, resolved = load_profile(json.dumps({'pma_model': p}).encode(), READ_CONTEXT)
    assert resolved == dict(p, temperature=1)
    _, legacy = load_profile(json.dumps({'claude_monitor_opus48': p}).encode(), 'U')
    assert legacy == p and 'temperature' not in legacy


@pytest.mark.parametrize('bad', [True, False, None, '0.2', -0.1, 1.1, math.nan,
                                math.inf, -math.inf, 10**1000, [], {}])
def test_invalid_value_rejected_without_requests(bad):
    with pytest.raises(ValueError, match='temperature'):
        load_profile(json.dumps({'pma_model': profile(temperature=bad)}).encode(), READ_CONTEXT)


def test_gpt_temperature_remains_rejected():
    p = dict(provider='openai', api_mode='responses', model='gpt-6.1-sol',
        apibase='https://example.invalid', apikey='synthetic-only', store=False,
        reasoning_effort='high', max_tokens=8192, model_context_window=200000,
        read_timeout=300, max_retries=1, temperature=0.2)
    with pytest.raises(ValueError, match='unsupported'):
        load_profile(json.dumps({'pma_model': p}).encode(), READ_CONTEXT)


@pytest.mark.parametrize('temperature', [None, 0, 0.2, 0.5, 1])
def test_construct_requests_and_retry_keep_temperature_only_for_manager(
        tmp_path, monkeypatch, temperature):
    from episode import construct_upstream
    from harbor.llms import lite_llm
    import claude_memory_retry
    from test_predictive_memory_read import run
    p = profile() if temperature is None else profile(temperature=temperature)
    original = copy.deepcopy(p)
    host = construct_upstream(tmp_path/'agent', research_candidate=READ_CONTEXT, memory_profile=p)
    requested = 1 if temperature is None else temperature
    seen = []
    replies = iter([
        {'content':'Read.', 'tool_calls':[{'id':'r','type':'function','function':{
            'name':'memory_read','arguments':'{"bank_id":"knowledge"}'}}]},
        {'content':'Nothing else to preserve or remind.'}])
    async def completion(**kwargs):
        seen.append(copy.deepcopy(kwargs))
        if len(seen) == 1:
            raise ConnectionError('synthetic transient failure')
        return {'choices':[{'message':next(replies),'finish_reason':'stop'}],
                'usage':{'prompt_tokens':1,'completion_tokens':1}}
    async def no_sleep(_):
        pass
    monkeypatch.setattr(lite_llm.litellm, 'acompletion', completion)
    monkeypatch.setattr(claude_memory_retry.asyncio, 'sleep', no_sleep)
    result = run(host._memory_agent)
    assert len(seen) == 3
    assert all(req['temperature'] == requested for req in seen)
    assert all(req['drop_params'] is True for req in seen)  # existing SDK policy, not changed
    assert all(req['thinking'] == {'type':'adaptive'} for req in seen)
    assert all(req['reasoning_effort'] == 'high' for req in seen)
    assert all(req['max_tokens'] == 8192 for req in seen)
    assert all('tool_choice' not in req for req in seen)  # no forced selection
    assert all({t['function']['name'] for t in req['tools']} ==
               {'memory_read','memory_add','send_reminder'} for req in seen)
    assert host._llm.calls == 0 and p == original
    assert result.termination == 'wake_no_tool'
    assert host._memory_llm._temperature == requested


def test_direct_constructor_rejects_invalid_config(tmp_path):
    from episode import construct_upstream
    with pytest.raises(ValueError, match='temperature'):
        construct_upstream(tmp_path/'agent', research_candidate=READ_CONTEXT,
                           memory_profile=profile(temperature=True))


def test_legacy_manager_constructor_default_does_not_change(tmp_path):
    from episode import construct_upstream
    host = construct_upstream(tmp_path/'agent', research_candidate='pma_predictive_f838_v1',
                              memory_profile=profile())
    assert host._memory_llm._temperature == 0.3
    assert host._llm.calls == 0


def test_source_identity_already_covers_both_changed_modules():
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = root / 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/single_run_certification.py'
    names = {'SOURCE_FILES', 'PREDICTIVE_SOURCE_FILES',
             'CONTEXT_PREDICTIVE_SOURCE_FILES', 'READ_CONTEXT_PREDICTIVE_SOURCE_FILES'}
    scope = {'V3_SOURCE_FILES': ()}
    for node in ast.parse(source.read_text()).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') in names:
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
    paths = scope['READ_CONTEXT_PREDICTIVE_SOURCE_FILES']
    for filename in ['episode.py', 'pma_model_profile.py']:
        assert any(path.endswith('/' + filename) for path in paths)
