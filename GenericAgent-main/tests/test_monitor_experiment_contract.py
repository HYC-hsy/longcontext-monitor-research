import json

import pytest

from monitor_agent_core.experiment_contract import (
    load_contract, validate_live_roles,
)


def contract_path():
    from monitor_agent_core import experiment_contract
    return experiment_contract.Path(experiment_contract.__file__).with_name(
        "dual_opus_contract.json")


def resolved_roles():
    contract = load_contract(contract_path())
    return contract, dict(contract["roles"]["task_agent"]["resolved"]), dict(
        contract["roles"]["supervisor"]["resolved"])


def test_wrong_task_or_supervisor_is_rejected_before_request():
    contract, task, supervisor = resolved_roles()
    requests = []
    task["model"] = "claude-opus-4-6"
    with pytest.raises(ValueError, match="role=task_agent field=model"):
        validate_live_roles(contract, task, supervisor)
    assert requests == []
    task = dict(contract["roles"]["task_agent"]["resolved"])
    supervisor["model"] = "gpt-5.6-sol"
    with pytest.raises(ValueError, match="role=supervisor field=model"):
        validate_live_roles(contract, task, supervisor)
    assert requests == []


def test_independent_c_profile_or_different_config_is_rejected():
    contract, task, supervisor = resolved_roles()
    with pytest.raises(ValueError, match="must inherit supervisor"):
        validate_live_roles(contract, task, supervisor, "old-default")
    child = dict(supervisor, model="gpt-5.6-sol")
    with pytest.raises(ValueError, match="role=independent_c field=model"):
        validate_live_roles(contract, task, supervisor, child=child)


def test_resolved_contract_contains_no_credentials():
    contract, task, supervisor = resolved_roles()
    result = validate_live_roles(contract, task, supervisor)
    encoded = json.dumps(result)
    assert "apikey" not in encoded
    assert "authorization" not in encoded.lower()
