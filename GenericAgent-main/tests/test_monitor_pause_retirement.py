import pytest

from ga_monitor_adapter import GenericAgentMonitorAdapter
from monitor_agent_core.runtime import MonitorRuntime


def test_old_manifest_cannot_silently_enable_removed_pause(monkeypatch):
    monkeypatch.setenv('GA_MONITOR_HYBRID_CONTROL', '1')
    with pytest.raises(ValueError, match='retired'):
        GenericAgentMonitorAdapter()


def test_direct_runtime_rejects_retired_configuration(tmp_path):
    with pytest.raises(ValueError, match='retired'):
        MonitorRuntime(task_id='fixture', public_task='Task', task_workspace=tmp_path / 'workspace',
                       artifact_dir=tmp_path / 'artifacts', config_name='fixture',
                       model_config={'monitor_hybrid_control': True},
                       interrupt_callback=lambda _: None)
    assert not (tmp_path / 'artifacts').exists()
