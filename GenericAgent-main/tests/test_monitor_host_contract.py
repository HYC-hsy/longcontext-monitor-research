import json
import subprocess
import sys
from pathlib import Path

import pytest

from ga_monitor_adapter import public_observation
from monitor_agent_core.configuration import load_profile
from monitor_agent_core.runtime import MonitorRuntime


def test_adapter_translates_without_changing_public_content():
    packet = {'internal_turn': 9, 'response_content': '<summary>Inspect tests</summary>\nfull text',
              'tool_calls': [{'tool_name': 'code_run', 'arguments': {'code': 'print(1)'}}],
              'tool_results': [{'stdout': '1'}]}
    event = public_observation(packet)
    assert event['task_turn'] == 9
    assert event['text'] == packet['response_content']
    assert event['synopsis'] == 'Inspect tests'
    assert event['tool_calls'][0]['name'] == 'code_run'
    assert event['tool_calls'][0]['arguments'] == packet['tool_calls'][0]['arguments']
    assert event['tool_results'] == packet['tool_results']
    assert 'internal_turn' not in event
    assert 'tool_name' in packet['tool_calls'][0]  # Input not mutated.


def test_profile_location_is_explicit(monkeypatch):
    monkeypatch.delenv('MONITOR_CONFIG_FILE', raising=False)
    with pytest.raises(ValueError, match='explicit'):
        load_profile('anything')


def test_adapter_owns_task_requirements_copy(tmp_path, monkeypatch):
    import ga_monitor_adapter as adapter
    captured = {}
    monkeypatch.setattr(adapter, 'MonitorRuntime', lambda **kw: captured.update(kw))
    adapter.GenericAgentMonitorAdapter(task_workspace=tmp_path, public_task='Original', model_config={})
    path = Path(captured['task_original_path'])
    assert path.parent == tmp_path
    assert path.read_text(encoding='utf-8') == 'Original'
    assert captured['task_id']


def test_mismatched_task_history_rejected_before_process_start(tmp_path):
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    (artifacts / 'task_identity.json').write_text(json.dumps({'task_id': 'old'}))
    with pytest.raises(ValueError, match='different task'):
        MonitorRuntime(task_id='new', public_task='Task', task_workspace=workspace,
            artifact_dir=artifacts, config_name='fixture', model_config={}, interrupt_callback=lambda _: None)
    assert list(workspace.iterdir()) == []


def test_noargs_only_tolerated_for_no_parameter_action(tmp_path):
    from monitor_agent_core.agent import MonitorAgent
    from monitor_agent_core.workspace import MonitorWorkspace
    from monitor_agent_core.provider import MonitorProviderClient
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    client = MonitorProviderClient('fixture', dict(apikey='TEST', apibase='https://example.invalid', model='test'))
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, tmp_path / 'private'))
    monitor.completion_pending = True
    assert monitor.dispatch('allow_complete', {'_noargs': 'unused'}).action.kind == 'allow_complete'
    assert monitor.dispatch('allow_complete', {'approve_all': True}).action is None
    assert monitor.dispatch('intervene', {'_noargs': 'unused'}).action is None


def test_installed_package_runs_without_ga(tmp_path):
    import shutil
    source = tmp_path / 'source'
    core = Path(__file__).resolve().parents[1] / 'monitor_agent_core'
    shutil.copytree(core, source, ignore=shutil.ignore_patterns('__pycache__', '*.local.json'))
    wheel_dir = tmp_path / 'wheels'
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                    '--no-index', '-w', str(wheel_dir), str(source)], check=True, capture_output=True)
    target = tmp_path / 'installed'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-deps', '--no-index',
                    '--target', str(target), str(next(wheel_dir.glob('*.whl')))], check=True, capture_output=True)
    code = '''
import sys, threading, time, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from monitor_agent_core.runtime import MonitorRuntime
from monitor_agent_core.provider import MonitorProviderClient, ModelResponse, ToolCall
class Process:
    def __init__(self, target, args, daemon): self.t=threading.Thread(target=target,args=args,daemon=daemon)
    def start(self): self.t.start()
    def join(self,timeout): self.t.join(timeout)
    def is_alive(self): return self.t.is_alive()
    def terminate(self): raise AssertionError('Worker did not close')
calls=[]
def complete(self,messages,tools):
    calls.append(messages)
    return ModelResponse('',[ToolCall('w'+str(len(calls)), 'wait', '{"after_turns":1}')],{})
MonitorProviderClient.complete=complete
root=Path(sys.argv[2]); workspace=root/'workspace'; workspace.mkdir()
runtime=MonitorRuntime(task_id='standalone',public_task='Inspect public tests',task_workspace=workspace,
    artifact_dir=root/'artifacts',config_name='fixture',model_config={'apikey':'TEST','apibase':'https://example.invalid','model':'test'},
    interrupt_callback=lambda text:None,process_factory=Process)
try:
    deadline=time.monotonic()+5
    receipt_path=runtime.artifact_dir/'runtime_receipts.jsonl'
    def ready():
        if not receipt_path.exists():return False
        return any(json.loads(line).get('kind')=='ready'
                   for line in receipt_path.read_text().splitlines() if line.endswith('}'))
    while not ready() and time.monotonic()<deadline:time.sleep(.02)
    assert ready()
    assert calls
    runtime.archive_boundary({'task_turn':1,'text':'I will inspect tests','synopsis':'Inspect tests','tool_calls':[],'tool_results':[]})
    while len(calls)<2 and time.monotonic()<deadline:time.sleep(.02)
    assert len(calls)>=2
    assert not list(workspace.iterdir())
    assert not {'ga','agentmain','agent_loop','llmcore','mykey','research_runtime'}.intersection(sys.modules)
finally:runtime.close()
print('independent lifecycle passed')
'''
    result = subprocess.run([sys.executable, '-I', '-c', code, str(target), str(tmp_path)],
                            cwd=tmp_path, check=True, capture_output=True, text=True, timeout=20)
    assert 'independent lifecycle passed' in result.stdout
