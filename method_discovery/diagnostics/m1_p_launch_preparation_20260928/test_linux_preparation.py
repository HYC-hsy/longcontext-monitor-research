"""Pure/fake checks of optional budget bypass and locked thin launch entry."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

from prepare_bundle import M1, TASK, blob, POLICY_COMMIT, POLICY_PATH, sha
from launch_pilot import common_profiles, authorize, ORDER


def test_shared_config_is_archived_not_small_prototype_budget():
    cfg = common_profiles()
    assert cfg['native_claude_cc_vibe_opus48']['max_tokens'] == 64000
    assert cfg['claude_monitor_opus48']['max_tokens'] == 8192
    assert cfg['claude_monitor_opus48']['monitor_dcec'] is True
    assert cfg['claude_monitor_opus48']['monitor_dcec_working_chars'] == 4000
    assert all(x['max_retries'] == 8 and x['model'] == 'claude-opus-4-8' for x in cfg.values())
    assert len(ORDER) == 4 and len({x[0] for x in ORDER}) == 4


def test_authorization_fails_closed_and_binds_sources(tmp_path):
    with pytest.raises(RuntimeError): authorize(None, ORDER[0][0])
    path = tmp_path / 'authorization.json'
    path.write_text(json.dumps({'authorization': True, 'records': [ORDER[0][0]]}))
    with pytest.raises(RuntimeError): authorize(path, ORDER[0][0])
    auth = dict(authorization=True, records=[ORDER[0][0]], supervisor_commit=M1, task_commit=TASK,
        policy_sha256=sha(blob(POLICY_COMMIT, POLICY_PATH)),
        launcher_sha256=sha((Path(__file__).parent / 'launch_pilot.py').read_bytes()))
    path.write_text(json.dumps(auth))
    assert authorize(path, ORDER[0][0]) == auth
    with pytest.raises(RuntimeError): authorize(path, ORDER[1][0])


def test_budget_off_does_not_install_task_transport_wrapper(tmp_path, monkeypatch):
    import pilot_bootstrap
    import requests
    class FakeSession:
        def raw_ask(self, messages): return iter(['unchanged'])
    fake = SimpleNamespace(NativeClaudeSession=FakeSession, _record_usage=lambda *args: None)
    monkeypatch.setitem(sys.modules, 'llmcore', fake)
    monkeypatch.setattr(pilot_bootstrap, 'install', lambda root: None)
    (tmp_path / 'pilot_binding.json').write_text(json.dumps({'budget_enabled': False}))
    original_post, original_raw, original_usage = requests.post, FakeSession.raw_ask, fake._record_usage
    pilot_bootstrap.install_task(tmp_path)
    assert requests.post is original_post
    assert FakeSession.raw_ask is original_raw and fake._record_usage is original_usage
    assert not (tmp_path / 'resource_audit.json').exists()
