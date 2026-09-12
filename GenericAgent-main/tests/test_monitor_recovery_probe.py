import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'method_discovery'))
import probe_monitor_auto_recovery as probe
from probe_curl_tool_matrix import payload_for


def test_fixed_request_is_auto_high_streaming():
    request = payload_for('C')
    assert request['tool_choice'] == 'auto'
    assert request['model'] == 'gpt-5.6-sol'
    assert request['reasoning'] == {'effort': 'high'}
    assert request['stream'] is True and request['store'] is False
    assert request['tools'][0]['name'] == 'get_probe_token'


def test_prepare_only_does_not_load_credentials_or_request(monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['probe', '--prepare-only'])
    def forbidden():
        raise AssertionError('Must not request')
    monkeypatch.setattr(probe, 'matrix_main', forbidden)
    assert probe.main() == 0
    assert json.loads(capsys.readouterr().out) == payload_for('C')
