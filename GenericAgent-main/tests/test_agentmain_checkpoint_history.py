import json
from types import SimpleNamespace

from agentmain import checkpoint_turn_offset, restore_history_file


def agent():
    return SimpleNamespace(llmclient=SimpleNamespace(
        backend=SimpleNamespace(history=[]), last_tools="",
    ))


def test_restore_checkpoint_session_extracts_history_and_tools(tmp_path):
    target = agent()
    path = tmp_path / "session.json"
    path.write_text(json.dumps({
        "history": [{"role": "assistant", "content": "proposal"}],
        "last_tools": "tools-at-boundary", "system": "archived-system",
    }), encoding="utf-8")
    restored = restore_history_file(target, path)
    assert target.llmclient.backend.history == restored["history"]
    assert target.llmclient.last_tools == "tools-at-boundary"


def test_restore_legacy_history_remains_compatible(tmp_path):
    target = agent()
    path = tmp_path / "history.json"
    path.write_text(json.dumps([{"role": "user", "content": "task"}]), encoding="utf-8")
    restore_history_file(target, path)
    assert target.llmclient.backend.history[0]["role"] == "user"


def test_checkpoint_turn_offset_reads_global_boundary_turn(tmp_path):
    (tmp_path / "packet.json").write_text(json.dumps({
        "boundary": "pre_completion_decision",
        "identity": {"internal_turn": 56},
    }), encoding="utf-8")
    assert checkpoint_turn_offset(tmp_path) == 56


def test_checkpoint_turn_offset_rejects_missing_identity(tmp_path):
    (tmp_path / "packet.json").write_text(json.dumps({
        "boundary": "pre_completion_decision", "identity": {},
    }), encoding="utf-8")
    try:
        checkpoint_turn_offset(tmp_path)
    except ValueError as error:
        assert "global internal_turn" in str(error)
    else:
        raise AssertionError("invalid checkpoint turn must be rejected")
