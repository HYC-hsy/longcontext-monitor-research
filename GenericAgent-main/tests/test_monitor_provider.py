import json

from monitor_agent_core.provider import MonitorProviderClient


def config(model="claude-test", **overrides):
    return {
        "apikey": "test", "apibase": "https://example.test", "model": model,
        **overrides,
    }


def test_provider_kind_comes_from_explicit_config_or_model():
    assert MonitorProviderClient("anything", {**config(), "provider": "anthropic"}).provider == "anthropic"
    assert MonitorProviderClient("native_openai", config("gpt-5.6")).provider == "openai"


def test_anthropic_sse_preserves_thinking_signature_and_tool_call():
    client = MonitorProviderClient("native_claude", config())
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
        {"type": "content_block_start", "content_block": {"type": "thinking"}},
        {"type": "content_block_delta", "delta": {"type": "thinking_delta", "thinking": "inspect"}},
        {"type": "content_block_delta", "delta": {"type": "signature_delta", "signature": "signed"}},
        {"type": "content_block_stop"},
        {"type": "content_block_start", "content_block": {"type": "tool_use", "id": "c1", "name": "file_read"}},
        {"type": "content_block_delta", "delta": {"type": "input_json_delta", "partial_json": '{"path":"task/x"}'}},
        {"type": "content_block_stop"},
        {"type": "message_delta", "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ]
    lines = [("data: " + json.dumps(event)).encode() for event in events]
    blocks, usage = client._parse_anthropic(lines)
    assert blocks[0] == {"type": "thinking", "thinking": "inspect", "signature": "signed"}
    assert blocks[1]["input"] == {"path": "task/x"}
    assert usage == {"input_tokens": 10, "output_tokens": 5}


def test_openai_responses_sse_parses_text_and_function_call():
    client = MonitorProviderClient("native_openai", config("gpt-5.6"))
    events = [
        {"type": "response.output_item.done", "output_index": 0, "item": {
            "type": "reasoning", "id": "rs_1", "encrypted_content": "opaque",
        }},
        {"type": "response.output_text.delta", "delta": "checking"},
        {"type": "response.output_item.added", "output_index": 1, "item": {
            "type": "function_call", "call_id": "call-1", "name": "wait",
        }},
        {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": '{"after_turns":'},
        {"type": "response.function_call_arguments.done", "output_index": 1, "arguments": '{"after_turns":3}'},
        {"type": "response.completed", "response": {"usage": {"input_tokens": 20, "output_tokens": 4}}},
    ]
    blocks, usage = client._parse_openai_responses([
        ("data: " + json.dumps(event)).encode() for event in events
    ])
    assert blocks[0]["type"] == "openai_item"
    assert blocks[0]["item"]["encrypted_content"] == "opaque"
    assert blocks[1] == {"type": "text", "text": "checking"}
    assert blocks[2]["name"] == "wait"
    assert blocks[2]["input"] == {"after_turns": 3}
    assert usage["input_tokens"] == 20

    client.history = [{"role": "assistant", "content": blocks}]
    rebuilt = client._responses_history()
    assert rebuilt[1]["encrypted_content"] == "opaque"
    assert rebuilt[2]["type"] == "function_call"


def test_history_export_and_restore_are_independent_copies():
    first = MonitorProviderClient("native_claude", config())
    first.history = [{"role": "user", "content": [{"type": "text", "text": "state"}]}]
    exported = first.export_history()
    second = MonitorProviderClient("native_claude", config())
    second.restore_history(exported)
    exported[0]["content"][0]["text"] = "mutated"
    assert second.history[0]["content"][0]["text"] == "state"


def test_large_window_compaction_keeps_initialization_and_recent_repair():
    client = MonitorProviderClient(
        "native_openai", config("gpt-5.6-sol", monitor_history_char_limit=6000)
    )
    initialization = [
        {"role": "user", "content": [{"type": "text", "text": "initialize"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "root model"}]},
        {"role": "user", "content": [{"type": "text", "text": "first patrol"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "wait"}]},
    ]
    middle = []
    for index in range(12):
        middle.extend([
            {"role": "user", "content": [{
                "type": "tool_result", "tool_use_id": f"old-{index}",
                "content": "x" * 1500,
            }]},
            {"role": "assistant", "content": [{"type": "text", "text": f"old-{index}"}]},
        ])
    recent = []
    for index in range(8):
        recent.extend([
            {"role": "user", "content": [{"type": "text", "text": f"repair-{index}"}]},
            {"role": "assistant", "content": [{"type": "text", "text": f"observe-{index}"}]},
        ])
    client.history = initialization + middle + recent

    client._compact_history()

    assert client.history[:4] == initialization
    assert client.history[-16:] == recent
    assert [item["role"] for item in client.history] == [
        "user" if index % 2 == 0 else "assistant"
        for index in range(len(client.history))
    ]
    assert client.history_transforms[-1]["removed_messages"] > 0
    assert client.history_measure()["characters"] <= client.history_char_limit


def test_gpt56_default_monitor_budget_is_wider_than_ga_baseline():
    client = MonitorProviderClient(
        "native_openai", config("gpt-5.6-sol", context_win=200000)
    )
    assert client.history_char_limit == 700000


def test_telemetry_drain_is_incremental():
    client = MonitorProviderClient("native_openai", config("gpt-5.6-sol"))
    client.usage_records.append({"input_tokens": 30, "output_tokens": 4})
    client.history_transforms.append({"kind": "monitor_history_compaction"})

    first = client.drain_telemetry()
    second = client.drain_telemetry()

    assert first["usage"] == [{"input_tokens": 30, "output_tokens": 4}]
    assert first["history_transforms"] == [{"kind": "monitor_history_compaction"}]
    assert second == {"usage": [], "history_transforms": []}
