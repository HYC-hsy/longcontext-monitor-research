import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import m0_deliberative_monitor as m0
from ga import GenericAgentHandler


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.message_batches = []
        self.max_tokens = 1024
        self.reasoning_effort = "xhigh"

    def raw_ask(self, messages):
        # M0 is one persistent conversation. Record the newest review or
        # protocol-correction turn, not the immutable policy at index zero.
        self.message_batches.append(messages)
        self.prompts.append(messages[-1]["content"][0]["text"])
        yield json.dumps(self.responses.pop(0))


class RawSession(FakeSession):
    def raw_ask(self, messages):
        self.message_batches.append(messages)
        self.prompts.append(messages[-1]["content"][0]["text"])
        yield self.responses.pop(0)


class MixedSession(FakeSession):
    """Decision dictionaries plus raw natural-language maintenance responses."""
    def raw_ask(self, messages):
        self.message_batches.append(messages)
        self.prompts.append(messages[-1]["content"][0]["text"])
        value = self.responses.pop(0)
        yield value if isinstance(value, str) else json.dumps(value)


def v2_decision(*, intervention="", attention_mode="patrol", completion=None,
                **overrides):
    value = {
        "intervention_message": intervention,
        "attention": {
            "mode": attention_mode,
            "reason": "test fixture attention choice",
        },
        "termination_decision": completion or (
            "continue_task" if intervention else "allow_complete"
        ),
        "epistemic_status": "confirmed_conflict" if intervention else "watch",
        "intervention_mode": "repair" if intervention else "none",
        "imminent_action_anchor": "",
        "reason": "public reason",
        "public_anchors": ["task clause"],
        "discrepancy": "",
        "exit_condition": "",
        "authority_basis": "correctness_evidence" if intervention else "none",
        "material_task_impact": "The public task can be completed incorrectly." if intervention else "",
        "why_silence_is_insufficient": "The next action would close over the discrepancy." if intervention else "",
        "evidence_availability": "obtainable_now" if intervention else "not_applicable",
        "next_safe_action": "Run the public discriminating probe." if intervention else "",
        "unresolved_unknown": "",
        "notes": "persistent notes",
    }
    value.update(overrides)
    return value


def decision(action, **overrides):
    """Compatibility adapter for historical tests; new protocol tests use v2_decision."""
    intervention = str(overrides.pop("message", ""))
    attention_mode = overrides.pop(
        "attention_mode", "focused" if action in {"HOLD", "ABSTAIN"} else "patrol"
    )
    if action in {"HOLD", "ABSTAIN"} and not intervention:
        intervention = "Address the supported public discrepancy before proceeding."
    return v2_decision(
        intervention=intervention, attention_mode=attention_mode, **overrides
    )


def root_audit(a="supported", b="supported"):
    return [
        {"obligation_id": "obligation:0000", "obligation": "Implement A", "status": a,
         "public_evidence": ["A implementation and discriminating test"] if a == "supported" else []},
        {"obligation_id": "obligation:0001", "obligation": "Implement B", "status": b,
         "public_evidence": ["B implementation and discriminating test"] if b == "supported" else []},
    ]


def packet(turn=1):
    return {
        "boundary": "post_tool_pre_next_llm",
        "internal_turn": turn,
        "response_content": "I think the current subgoal is complete.",
        "tool_calls": [{"tool_name": "file_patch", "args": {"path": "x.py"}}],
        "tool_results": ["patch applied"],
    }


def build_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
    )
    # Most unit tests exercise post-initialization control behavior. Tests of
    # first-boundary ledger construction explicitly clear this seed.
    monitor.root_obligation_audit = root_audit()
    return monitor, session




def build_semantic_files_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def test_semantic_files_use_generic_scoped_file_operations(monkeypatch, tmp_path):
    monitor, _ = build_semantic_files_monitor(monkeypatch, tmp_path, [])
    listed = monitor._inspect_monitor_files({
        "operation": "list_files", "scope": "monitor",
    })
    assert listed["ok"] is True
    assert any(row["path"] == "state/working_state.md" for row in listed["files"])
    opened = monitor._inspect_monitor_files({
        "operation": "read_file", "scope": "monitor",
        "path": "state/working_state.md",
    })
    changed = monitor._inspect_monitor_files({
        "operation": "edit_file", "scope": "monitor",
        "path": "state/working_state.md",
        "expected_sha256": opened["sha256"],
        "edits": [{
            "old_text": "# Working state",
            "new_text": "# Working state\n\nA is currently supported.",
        }],
    })
    assert changed["ok"] is True
    searched = monitor._inspect_monitor_files({
        "operation": "search_text", "scope": "monitor", "pattern": "supported",
    })
    assert searched["ok"] is True
    assert searched["matches"][0]["path"] == "state/working_state.md"


def test_semantic_files_prompt_exposes_capability_not_fixed_ritual(monkeypatch, tmp_path):
    monitor, _ = build_semantic_files_monitor(monkeypatch, tmp_path, [])
    prompt = monitor._base_prompt()
    assert "PERSISTENT NATURAL-LANGUAGE WORKSPACE" in prompt
    assert "not a fixed schema" in prompt
    assert "do not perform a fixed" in prompt
    assert "reopen the claim in ordinary language" in prompt
    assert "version history preserve what was previously believed" in prompt
    assert "scope=monitor" in prompt
    assert "framework-specific internal class" in prompt
    for implementation_label in ("M0", "M1", "M2", "M3-A", "M3-B", "M3-C", "M3-D", "M3.2", "M3.5"):
        assert implementation_label not in prompt
    schema = monitor._decision_schema(completion=True)
    assert "root_obligation_updates" not in schema
    assert "root_obligation_audit" not in schema


def test_all_current_prompt_surfaces_are_task_focused(monkeypatch, tmp_path):
    monitor, session = build_semantic_files_monitor(monkeypatch, tmp_path, [{
        "task_model": (
            "Preserve both explicit deliverables. Neither has execution evidence yet, "
            "so both remain unresolved."
        ),
        "working_note": "I need to retain both deliverables and observe how they are evidenced.",
        "observation_plan": {
            "review_after_turns": 8,
            "focus": "the first material implementation decision",
            "expected_progress": "an implementation or test boundary",
            "reason": "early work can reveal the task interpretation",
        },
        "notes": "Waiting for public execution evidence.",
    }])
    assert monitor.bootstrap_task_state() == {"status": "initialized"}
    surfaces = [
        monitor._base_prompt(),
        session.prompts[-1],
        monitor._minimal_wake_prompt(packet(1)),
        monitor._incremental_inspection_prompt(
            [{"result": {"ok": True}}], packet(1)
        ),
    ]
    forbidden = (
        "M0", "M1", "M2", "M3-A", "M3-B", "M3-C", "M3-D",
        "M3.2", "M3.5", "GenericAgent", "root_obligation_audit",
        "workspace_delta",
    )
    for surface in surfaces:
        for label in forbidden:
            assert label not in surface
        assert "\ufffd" not in surface
    task_model = (tmp_path / "monitor" / "semantic_files" / "state" /
                  "task_model.md").read_text(encoding="utf-8")
    assert "Preserve both explicit deliverables" in task_model
    assert "obligation:" not in task_model


def test_review_can_read_edit_receive_receipt_then_decide(monkeypatch, tmp_path):
    monitor, session = build_semantic_files_monitor(monkeypatch, tmp_path, [])
    initial = monitor._inspect_monitor_files({
        "operation": "read_file", "path": "state/working_state.md",
    })
    session.responses.extend([
        {
            "action": "INSPECT", "reason": "Recover my durable working state.",
            "inspection": {
                "operation": "read_file", "scope": "monitor",
                "path": "state/working_state.md",
            },
        },
        {
            "action": "INSPECT", "reason": "Persist the material observation.",
            "inspection": {
                "operation": "edit_file", "scope": "monitor",
                "path": "state/working_state.md",
                "expected_sha256": initial["sha256"],
                "edits": [{
                    "old_text": "# Working state",
                    "new_text": "# Working state\n\nThe current local change is provisional.",
                }],
            },
        },
        v2_decision(),
    ])
    assert monitor.review(packet(4)) == ""
    result = monitor.decisions[-1]
    assert result["intervention_message"] == ""
    assert len(result["inspections"]) == 2
    assert result["inspections"][1]["result"]["changed"] is True
    persisted = monitor._inspect_monitor_files({
        "operation": "read_file", "path": "state/working_state.md",
    })
    assert "current local change is provisional" in persisted["content"]


def build_m2_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
    )
    monitor.root_obligation_audit = root_audit()
    assert monitor.session.total_response_timeout == 300.0
    return monitor, session


def build_m3a_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
        m3_human_loop_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_m3b_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
        m3_human_loop_enabled=True,
        m3_decision_value_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_m3c_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor-m3c",
        m3_human_loop_enabled=True,
        m3_discriminative_control_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_m3d_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor-m3d",
        m3_human_loop_enabled=True,
        m3_discriminative_control_enabled=True,
        m3_combined_control_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session




def test_m3c_accepts_one_natural_working_inquiry_during_confirmed_conflict(
        monkeypatch, tmp_path):
    response = v2_decision(
        intervention="The implementation is wrong; run the bounded comparison next.",
        attention_mode="focused",
        epistemic_status="confirmed_conflict",
        discrepancy="The public implementation conflicts with the contract.",
        discriminative_step=(
            "I am comparing whether the failed observation comes from the repair "
            "or its oracle; reconsider after the unchanged control returns."
        ),
    )
    monitor, _ = build_m3c_monitor(monkeypatch, tmp_path, [response])

    monitor.review(packet())

    assert monitor.discriminative_step["working_inquiry"].startswith("I am comparing")
    assert monitor.discriminative_step["intervened"] is True
    prompt = monitor._base_prompt()
    assert "bounded comparison" in prompt
    assert "reasonable behavioral uptake" in prompt


def test_m3c_releasing_repair_clears_omitted_natural_inquiry(monkeypatch, tmp_path):
    correction = v2_decision(
        intervention="Stop and compare the implementation with the public contract.",
        attention_mode="focused",
        discrepancy="The implementation conflicts with the public contract.",
        discriminative_step="I am waiting for the bounded contract comparison.",
    )
    released = v2_decision(attention_mode="patrol")
    monitor, _ = build_m3c_monitor(monkeypatch, tmp_path, [correction, released])

    monitor.review(packet())
    assert monitor.open_episode is not None
    assert monitor.discriminative_step is not None

    monitor.review(packet(turn=2))

    assert monitor.open_episode is None
    assert monitor.discriminative_step is None
    assert monitor.checkpoints.load()["m3_discriminative_step"] is None


def test_m3d_closes_decision_sufficient_inquiry_without_closing_root(
        monkeypatch, tmp_path):
    opened = v2_decision(
        attention_mode="focused",
        epistemic_status="causal_uncertainty",
        discriminative_step=(
            "I am comparing production behavior with the test oracle because opposite "
            "results change whether I repair code or the test; reconsider after one control run."
        ),
    )
    closed = v2_decision(
        attention_mode="patrol",
        reason="The control run supports the required behavior; exact callback count changes no action.",
        unresolved_unknown="Exact callback count remains unknown but is not required.",
        discriminative_step="",
    )
    monitor, _ = build_m3d_monitor(monkeypatch, tmp_path, [opened, closed])
    first = packet()
    first["archive_delta"] = {"last_sequence": 10}
    monitor.review(first)

    wake = packet(turn=2)
    wake["archive_delta"] = {"last_sequence": 14}
    prompt = monitor._minimal_wake_prompt(wake)
    assert '"bounded_inquiry_open":true' in prompt
    assert '"public_activity_since_inquiry_review":true' in prompt

    monitor.review(wake)

    assert monitor.discriminative_step is None
    assert monitor.last_closed_inquiry["status"] == "decision_sufficient"
    assert "callback count" in monitor.last_closed_inquiry["resolution_reason"]
    checkpoint = monitor.checkpoints.load()
    assert checkpoint["m3d_last_closed_inquiry"]["closed_archive_sequence"] == 14
    assert checkpoint["m3_discriminative_step"] is None

    restored = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m3d",
        m3_human_loop_enabled=True,
        m3_discriminative_control_enabled=True, m3_combined_control_enabled=True,
    )
    assert restored.discriminative_step is None
    assert restored.last_closed_inquiry["status"] == "decision_sufficient"


def test_m3d_switches_inquiry_without_expanding_the_old_one(monkeypatch, tmp_path):
    first = v2_decision(
        attention_mode="focused",
        discriminative_step="I am testing whether A or its oracle caused the failure.",
    )
    second = v2_decision(
        attention_mode="focused",
        reason="A is resolved; B now has a distinct action-relevant ambiguity.",
        discriminative_step="I am testing whether B preserves the required public ordering.",
    )
    monitor, _ = build_m3d_monitor(monkeypatch, tmp_path, [first, second])
    p1 = packet()
    p1["archive_delta"] = {"last_sequence": 3}
    p2 = packet(turn=2)
    p2["archive_delta"] = {"last_sequence": 8}

    monitor.review(p1)
    monitor.review(p2)

    assert monitor.last_closed_inquiry["status"] == "switched"
    assert "A or its oracle" in monitor.last_closed_inquiry["inquiry"]
    assert "B preserves" in monitor.discriminative_step["working_inquiry"]
    assert monitor.discriminative_step["opened_archive_sequence"] == 8


def test_m3d_requires_c_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))
    with pytest.raises(ValueError, match="requires the M3-C"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            artifact_dir=tmp_path / "invalid-combined-control",
            m3_human_loop_enabled=True, m3_combined_control_enabled=True,
        )


def build_m32_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m32",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_m35_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_h3_monitor(monkeypatch, tmp_path, responses, *, soft_limit=16000):
    session = MixedSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-h3",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
        history_soft_char_limit=soft_limit,
        history_target_characters=12000,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_h4_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-h4",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session










def test_m3a_missing_focus_does_not_retry_or_block(monkeypatch, tmp_path):
    monitor, session = build_m3a_monitor(
        monkeypatch, tmp_path, [decision("SILENT")]
    )

    assert monitor.review(packet()) == ""
    assert len(session.prompts) == 1
    assert "decision_focus" not in monitor.decisions[0]


def test_autonomous_wake_is_navigation_only_and_keeps_deeper_tools_available(
        monkeypatch, tmp_path):
    monitor, session = build_m3a_monitor(
        monkeypatch, tmp_path, [decision("SILENT", reason="coherent progress")]
    )
    monitor.observe_archived_boundaries([{
        "archive_event_id": "public_boundary_1", "internal_turn": 8,
        "boundary": "post_model_pre_tool",
        "response_content": "SECRET_INTENT: rewrite production from the failing test",
        "tool_calls": [{"tool_name": "file_patch", "args": {"path": "app.go"}}],
        "tool_results": [],
    }])

    first_look = monitor.baseline_observation(1)
    message = monitor.review({
        "archive_wake_only": True, "boundary": "autonomous_archive_observation",
        "internal_turn": 8,
        "archive_delta": {"new_boundaries": 1, "boundary_types": ["post_model_pre_tool"]},
        "baseline_observation": first_look,
        "response_content": "", "tool_calls": [], "tool_results": [],
    })

    assert message == ""
    assert len(session.prompts) == 1
    assert "SECRET_INTENT" not in session.prompts[0]
    assert "read_public_trajectory" in monitor._base_prompt()


def test_baseline_observation_coalesces_intent_and_result_boundaries(monkeypatch, tmp_path):
    monitor, _ = build_m3a_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    monitor.observe_archived_boundaries([
        {
            "archive_event_id": "pre", "internal_turn": 4,
            "boundary": "post_model_pre_tool", "response_content": "Run focused tests",
            "tool_calls": [{"tool_name": "code_run", "args": {"script": "go test ./x"}}],
            "tool_results": [],
        },
        {
            "archive_event_id": "post", "internal_turn": 4,
            "boundary": "post_tool_pre_next_llm", "response_content": "Run focused tests",
            "tool_calls": [{"tool_name": "code_run", "args": {"script": "go test ./x"}}],
            "tool_results": ["FAIL: contract mismatch"],
        },
    ])

    view = monitor.baseline_observation(2)

    assert view["observed_boundaries"] == 2
    assert view["observed_turns"] == 1
    assert len(view["events"]) == 1
    assert view["events"][0]["agent_response"] == "Run focused tests"
    assert view["events"][0]["tool_results"] == ["FAIL: contract mismatch"]


def test_first_look_is_size_bounded_and_omits_large_write_payloads(monkeypatch, tmp_path):
    monitor, _ = build_m3a_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    huge_source = "SECRET_FULL_SOURCE\n" + ("x" * 70000)
    monitor.observe_archived_boundaries([{
        "archive_event_id": "large-write", "internal_turn": 5,
        "boundary": "post_model_pre_tool", "response_content": "Write the implementation",
        "tool_calls": [{"tool_name": "file_write", "args": {
            "path": "src/large.py", "content": huge_source,
        }}], "tool_results": [],
    }])

    view = monitor.baseline_observation(1)
    encoded = json.dumps(view, ensure_ascii=False)

    assert view["included_characters"] <= view["character_budget"] == 24000
    assert "SECRET_FULL_SOURCE" not in encoded
    assert view["events"][0]["tool_calls"][0]["args_preview"]["path"] == "src/large.py"
    assert view["events"][0]["tool_calls"][0]["omitted_large_fields"] == ["content"]
    assert len(view["events"][0]["tool_calls"][0]["args_fingerprint"]) == 16
    # Bounded wake-up input must not destroy the exact append-only evidence.
    assert monitor.trajectory[0]["tool_calls"][0]["args"]["content"] == huge_source


def test_first_look_compacts_a_single_oversize_wide_event(monkeypatch, tmp_path):
    monitor, _ = build_m3a_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    wide_args = {f"option_{index}": "v" * 1000 for index in range(100)}
    monitor.observe_archived_boundaries([{
        "archive_event_id": "wide-call", "internal_turn": 6,
        "boundary": "post_model_pre_tool", "response_content": "Invoke a wide tool",
        "tool_calls": [{"tool_name": "wide_tool", "args": wide_args}],
        "tool_results": [],
    }])

    view = monitor.baseline_observation(1)

    assert view["included_characters"] <= view["character_budget"]
    assert view["events"][0]["oversize_event_compacted"] is True
    assert view["events"][0]["tool_calls"][0]["tool_name"] == "wide_tool"
    assert len(view["events"][0]["tool_calls"][0]["args_fingerprint"]) == 16


def test_m35_turn0_bootstrap_uses_only_task_and_initializes_unknown_state(
        monkeypatch, tmp_path):
    response = {
        "task_model": "Implement A and demonstrate B. Both are unresolved before execution.",
        "working_note": "I must preserve both explicit clauses until public evidence exists.",
        "observation_plan": {
            "review_after_turns": 12, "focus": "first material implementation evidence",
            "expected_progress": "an implementation and a discriminating test",
            "reason": "begin with a sparse patrol",
        },
        "notes": "initialized from task only",
    }
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [response])
    # If bootstrap accidentally consumes execution, this marker would reach the model.
    monitor.observe_archived_boundaries([{
        "archive_event_id": "not-for-bootstrap", "internal_turn": 1,
        "boundary": "post_model_pre_tool", "response_content": "SECRET_EXECUTION_MARKER",
        "tool_calls": [], "tool_results": [],
    }])

    result = monitor.bootstrap_task_state()

    assert result == {"status": "initialized"}
    assert len(session.prompts) == 1
    assert "ORIGINAL PUBLIC TASK" in session.prompts[0]
    assert "SECRET_EXECUTION_MARKER" not in session.prompts[0]
    assert "INSPECT" not in session.prompts[0]
    model = monitor.semantic_files.execute({
        "operation": "read_file", "path": "state/task_model.md",
    })
    assert "Both are unresolved" in model["content"]
    assert monitor.cognitive_checkpoint["reviewed_through_turn"] == 0
    assert monitor.cognitive_checkpoint["source"] == "turn0_task_bootstrap"
    assert monitor.observation_plan["review_after_turns"] == 12
    saved = json.loads((tmp_path / "monitor-m35" / "bootstrap_state.json").read_text(
        encoding="utf-8"
    ))
    assert saved["bootstrap_initialized"] is True
    assert saved["cognitive_checkpoint"]["reviewed_through_archive_sequence"] == 0


def test_m35_turn0_bootstrap_is_restored_without_a_second_model_call(monkeypatch, tmp_path):
    response = {
        "task_model": "Implement A and demonstrate B; neither has evidence yet.",
        "working_note": "Preserve both clauses and await public evidence.",
        "observation_plan": {"review_after_turns": 9},
        "notes": "initialized",
    }
    first, _ = build_m35_monitor(monkeypatch, tmp_path, [response])
    first.bootstrap_task_state()

    restored_session = FakeSession([])
    monkeypatch.setattr(m0, "resolve_session", lambda _: restored_session)
    restored = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )

    assert restored.bootstrap_task_state() == {"status": "restored"}
    assert restored_session.prompts == []
    assert restored.cognitive_checkpoint["continuation_note"].startswith("Preserve both")








def test_m32_missing_plan_uses_recovery_default_without_forcing_hold(monkeypatch, tmp_path):
    monitor, _ = build_m32_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    assert monitor.review(packet()) == ""
    assert monitor.observation_plan["review_after_turns"] == 20
    assert monitor.observation_plan["source"] == "default"


def test_m3b_missing_value_record_remains_valid_and_permissive(monkeypatch, tmp_path):
    monitor, session = build_m3b_monitor(
        monkeypatch, tmp_path, [decision("SILENT")]
    )

    assert monitor.review(packet()) == ""
    assert len(session.prompts) == 1
    assert "decision_value" not in monitor.decisions[0]


def test_malformed_monitor_json_gets_one_concise_protocol_retry(monkeypatch, tmp_path):
    session = RawSession([
        '{"action":"SILENT","reason":"missing delimiter"',
        json.dumps(decision("SILENT")),
    ])
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A.", workspace=tmp_path, config_name="fake",
        artifact_dir=tmp_path / "monitor",
    )
    monitor.root_obligation_audit = root_audit()

    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["intervention_message"] == ""
    assert len(session.prompts) == 2
    assert session.prompts[1].startswith("[PROTOCOL RETRY]")










































def test_inspect_then_hold_records_public_evidence(monkeypatch, tmp_path):
    (tmp_path / "test_contract.py").write_text("assert feature_a()\n", encoding="utf-8")
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "check test", "inspection": {
            "operation": "read_file", "path": "test_contract.py", "start_line": 1,
        }},
        decision(
            "HOLD", message="Feature B still lacks a behavioral probe.",
            discrepancy="B was dropped", exit_condition="run a discriminating B probe",
            notes="A has a provisional test; B remains contested.",
        ),
    ])

    prompt = monitor.review(packet())

    assert prompt == "Feature B still lacks a behavioral probe."
    assert monitor.open_episode["discrepancy"] == "B was dropped"
    assert monitor.attention_mode == "focused"
    assert "assert feature_a" in session.prompts[1]
    saved = json.loads((tmp_path / "monitor" / "decision_0001.json").read_text(encoding="utf-8"))
    assert saved["intervention_message"] == "Feature B still lacks a behavioral probe."
    assert saved["inspections"][0]["result"]["ok"] is True


def test_m35_inspection_results_are_appended_once_not_cumulatively_replayed(
        monkeypatch, tmp_path):
    (tmp_path / "a.txt").write_text("UNIQUE_RESULT_A", encoding="utf-8")
    (tmp_path / "b.txt").write_text("UNIQUE_RESULT_B", encoding="utf-8")
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "read A", "inspection": {
            "operation": "read_file", "path": "a.txt",
        }},
        {"action": "INSPECT", "reason": "read B", "inspection": {
            "operation": "read_file", "path": "b.txt",
        }},
        decision("SILENT"),
    ])

    assert monitor.review(packet()) == ""

    second_wire = json.dumps(session.message_batches[1], ensure_ascii=False)
    third_wire = json.dumps(session.message_batches[2], ensure_ascii=False)
    assert second_wire.count("UNIQUE_RESULT_A") == 1
    assert "UNIQUE_RESULT_B" not in second_wire
    assert third_wire.count("UNIQUE_RESULT_A") == 1
    assert third_wire.count("UNIQUE_RESULT_B") == 1
    assert "[MONITOR CONTINUATION]" in session.prompts[1]
    assert "UNIQUE_RESULT_A" not in session.prompts[2]
    assert "UNIQUE_RESULT_B" in session.prompts[2]


def test_large_inspection_result_is_exactly_archived_and_pageable(
        monkeypatch, tmp_path):
    monitor, _ = build_m35_monitor(monkeypatch, tmp_path, [])
    exact = {"ok": True, "content": "A" * 26000 + "TAIL_SENTINEL"}

    bounded = monitor._bounded_inspection_result(
        {"operation": "read_file", "path": "large.txt"}, exact
    )

    assert bounded["truncated"] is True
    assert bounded["total_characters"] > m0.INSPECTION_RESULT_ARCHIVE_THRESHOLD
    assert "TAIL_SENTINEL" not in bounded["content"]
    result_id = bounded["result_id"]
    archived = tmp_path / "monitor-m35" / "inspection_results" / f"{result_id}.json"
    assert json.loads(archived.read_text(encoding="utf-8")) == exact
    continuation = monitor._inspect_trajectory(bounded["continuation"])
    assert continuation["ok"] is True
    assert continuation["start_char"] == m0.INSPECTION_RESULT_PAGE_CHARACTERS
    pages = [bounded["content"], continuation["content"]]
    while continuation["truncated"]:
        continuation = monitor._inspect_trajectory(continuation["continuation"])
        pages.append(continuation["content"])
    assert "TAIL_SENTINEL" in "".join(pages)
    assert continuation["end_char"] == bounded["total_characters"]


def test_recent_delta_preserves_newest_uptake_when_older_write_is_oversized(
        monkeypatch, tmp_path):
    monitor, _ = build_h4_monitor(monkeypatch, tmp_path, [])
    monitor.observe_archived_boundaries([
        {
            "archive_event_id": "old-wide-write", "archive_sequence": 41,
            "internal_turn": 20, "boundary": "post_model_pre_tool",
            "response_content": "I will continue the old approach.",
            "tool_calls": [{"tool_name": "file_write", "args": {
                "path": "/app/wide.go", "content": "X" * 50000,
            }}], "tool_results": [],
        },
        {
            "archive_event_id": "new-uptake", "archive_sequence": 42,
            "internal_turn": 21, "boundary": "post_model_pre_tool",
            "response_content": "I accept the correction and am repairing Bytes now.",
            "tool_calls": [{"tool_name": "file_read", "args": {
                "path": "/app/data/binding/binditems.go",
            }}], "tool_results": [],
        },
    ])

    result = monitor._inspect_trajectory({
        "operation": "read_recent_delta", "limit": 20,
    })
    bounded = monitor._bounded_inspection_result(
        {"operation": "read_recent_delta", "limit": 20}, result
    )

    assert bounded.get("truncated") is not True
    assert result["latest_available_sequence"] == 42
    assert result["last_selected_sequence"] == 42
    assert "repairing Bytes now" in json.dumps(result, ensure_ascii=False)
    assert "X" * 100 not in json.dumps(result, ensure_ascii=False)






def test_h3_never_compacts_an_open_repair_episode(monkeypatch, tmp_path):
    monitor, _ = build_h3_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Correct B before encoding the current intent.",
            discrepancy="B intent conflicts with the public task.",
            exit_condition="B intent and action are aligned.",
        ),
        decision("SILENT", attention_mode="focused"),
        decision("SILENT", attention_mode="focused"),
    ])

    monitor.review(packet(1))
    protected_start = monitor.open_episode_history_start
    monitor.review(packet(2))
    monitor.review(packet(3))

    assert protected_start == 2
    assert monitor.open_episode_history_start == protected_start
    assert not (tmp_path / "monitor-h3" / "monitor_history_archives").exists()
    assert len(monitor.history) == 8










def test_verbal_acknowledgement_does_not_implicitly_release(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("HOLD", message="Show the unchanged global suite.", discrepancy="local only",
                 exit_condition="global suite passes"),
        decision("HOLD", message="Acknowledgement is not the requested run.", discrepancy="residual remains",
                 exit_condition="global suite passes"),
        decision("RELEASE", reason="new public global result", discrepancy="", exit_condition=""),
    ])

    assert monitor.review(packet(1))
    second = monitor.review(packet(2))
    assert second == "Acknowledgement is not the requested run."
    assert "M0 AUTHORITATIVE RECOVERY PACKAGE" not in second
    assert "Acknowledgement is not the requested run." in second
    assert monitor.open_episode is not None
    assert monitor.open_episode["opened_turn"] == 1
    assert monitor.open_episode["original_discrepancy"] == "local only"
    assert len(monitor.open_episode["challenges"]) == 2
    assert monitor.review(packet(3)) == ""
    assert monitor.open_episode is None
    assert monitor.attention_mode == "patrol"
    assert [bool(row["intervention_message"]) for row in monitor.decisions] == [True, True, False]


def test_silent_is_a_real_decision_and_does_not_open_episode(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT", notes="public signal is faithful")])
    assert monitor.review(packet()) == ""
    assert monitor.open_episode is None
    assert monitor.decisions[0]["intervention_message"] == ""
    assert monitor.attention_mode == "patrol"
    assert monitor.session.reasoning_effort == "high"


def test_same_persistent_history_is_used_across_reviews(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [decision("SILENT"), decision("SILENT")])
    monitor.review(packet(1))
    monitor.review(packet(2))
    assert len(session.prompts) == 2
    assert len(monitor.history) == 6
    assert "Original public task" not in session.prompts[1]


def test_public_trajectory_is_archived_but_not_eagerly_injected(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    monitor.review(packet(1))

    assert "recent_public_trajectory" not in session.prompts[0]
    rows = (tmp_path / "monitor" / "public_trajectory.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()
    saved = json.loads(rows[0])
    assert saved["internal_turn"] == 1
    assert saved["tool_calls"][0]["tool_name"] == "file_patch"
    assert saved["same_action_seen_before"] == 0








def test_public_archive_preserves_content_beyond_query_view_clip(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    value = packet(1)
    value["tool_results"] = ["start-" + ("x" * 8000) + "-end"]
    monitor.review(value)

    saved = json.loads((tmp_path / "monitor" / "public_trajectory.jsonl").read_text(
        encoding="utf-8"
    ))
    assert saved["tool_results"][0].endswith("-end")
    assert "M0 VIEW CLIPPED" not in saved["tool_results"][0]




def test_later_hold_cannot_redefine_original_repair_episode(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Resolve the count contradiction.",
            discrepancy="Public counts disagree.", exit_condition="Counts agree from source files.",
        ),
        decision(
            "HOLD", message="Perfect the auxiliary verifier headings.",
            discrepancy="Auxiliary verifier headings are incomplete.",
            exit_condition="Verifier checks every heading.",
        ),
    ])

    monitor.review(packet(1))
    monitor.review(packet(2))

    assert monitor.open_episode["original_discrepancy"] == "Public counts disagree."
    assert monitor.open_episode["discrepancy"] == "Public counts disagree."
    assert monitor.open_episode["original_exit_condition"] == "Counts agree from source files."
    assert monitor.open_episode["exit_condition"] == "Counts agree from source files."
    assert monitor.open_episode["current_residual"] == "Auxiliary verifier headings are incomplete."




def test_public_test_change_and_contract_search_tools(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    test_path = tmp_path / "feature_test.go"
    test_path.write_text("package x\n// clause: literal wildcard\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature_test.go"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=M0", "-c", "user.email=m0@example.invalid",
                    "commit", "-qm", "baseline"], cwd=tmp_path, check=True)
    test_path.write_text(
        "package x\n// clause: literal wildcard\nfunc TestWildcard(t *testing.T) {}\n",
        encoding="utf-8",
    )
    inspector = m0.PublicWorkspaceInspector(tmp_path)

    changed = inspector.execute({"operation": "list_changed_tests"})
    view = inspector.execute({"operation": "read_test_change", "path": "feature_test.go"})
    coverage = inspector.execute({"operation": "search_test_contract",
                                  "pattern": "literal wildcard"})

    assert changed["changed_tests"] == [{"status": " M", "path": "feature_test.go"}]
    assert "TestWildcard" in view["diff"]
    assert coverage["matches"][0]["path"] == "feature_test.go"


















def test_completion_abstain_with_executable_evidence_action_continues(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision(
            "ABSTAIN",
            message="Run the available comparison probe before closing.",
            evidence_availability="obtainable_now",
            next_safe_action="Run /testbed/reproduce.py with the installed interpreter.",
            root_obligation_audit=root_audit(b="unknown"),
        ),
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 26)

    assert result.decision == "CONTINUE"
    assert "available comparison probe" in result.next_prompt




def test_monitor_rejects_delegating_root_audit_to_task_agent(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD",
            message="Provide a root completion proposal that enumerates every clause in a global audit.",
            discrepancy="B is unsupported", exit_condition="B has a direct probe",
            root_obligation_audit=root_audit(b="unknown"),
        ),
        decision(
            "HOLD",
            message="The original clause requires B. Implement B and run its direct probe.",
            discrepancy="B is unsupported", exit_condition="B has a direct probe",
            root_obligation_audit=root_audit(b="unknown"),
        ),
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 27)

    assert result.decision == "CONTINUE"
    assert "Implement B" in result.next_prompt
    assert "Do not delegate the authoritative root audit" in session.prompts[1]


def test_agent_authored_audit_is_inferred_as_contested(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Repair B directly.", discrepancy="surrogate audit omitted B",
            exit_condition="B probe passes", next_safe_action="Implement and test B.",
        ),
    ])
    event = packet(29)
    event["response_content"] = (
        "I reconstructed the task in COMPLETE_IMPLEMENTATION_AUDIT.md from current tests."
    )

    monitor.review(event)

    assert "COMPLETE_IMPLEMENTATION_AUDIT.md" in monitor.contested_artifacts


def test_authority_loss_injects_complete_recovery_package(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Repair B and run its test.",
            discrepancy="The surrogate requirements omitted B.",
            exit_condition="B's original behavior passes a direct test.",
            next_safe_action="Discard the surrogate interpretation; implement and test B.",
            contested_artifacts=[{"path": "ROOT_AUDIT.md", "reason": "omits B"}],
        ),
    ])
    lost = packet(30)
    lost["response_content"] = "I cannot access the original task; please resend it."

    message = monitor.review(lost)

    assert "MONITOR AUTHORITATIVE RECOVERY PACKAGE" in message
    assert "Implement A and B; demonstrate both." in message
    assert "ROOT_AUDIT.md" in message
    assert "do not reconstruct or rewrite a global" in message.lower()
    assert monitor.recovery_level == 2
    assert monitor.contested_artifacts["ROOT_AUDIT.md"]["reason"] == "omits B"
    state = json.loads((tmp_path / "monitor" / "authoritative_state.json").read_text(
        encoding="utf-8"))
    assert state["recovery_level"] == 2
    assert "ROOT_AUDIT.md" in state["contested_artifacts"]


def test_repeated_hold_preserves_monitor_chosen_message(monkeypatch, tmp_path):
    repeated = decision(
        "HOLD", message="Repair the same contract conflict.",
        discrepancy="B was replaced by a nearby API.",
        exit_condition="The actual B API has a direct passing probe.",
        next_safe_action="Remove the substitute and exercise B directly.",
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [repeated, repeated])

    first = monitor.review(packet(1))
    second = monitor.review(packet(2))

    assert first == "Repair the same contract conflict."
    assert second == "Repair the same contract conflict."
    assert monitor.decisions[-1]["intervention_repeat_count"] == 2
    assert monitor.recovery_level == 0




def test_watch_hypothesis_cannot_hold_before_agent_runs_evidence(monkeypatch, tmp_path):
    speculative = decision(
        "HOLD", message="Rewrite the test before running it.",
        epistemic_status="watch", intervention_mode="repair",
        discrepancy="The startup helper might race.",
    )
    monitor, session = build_monitor(monkeypatch, tmp_path, [speculative, decision("SILENT")])

    message = monitor.review(packet(41))

    assert message == ""
    assert monitor.decisions[-1]["intervention_message"] == ""
    assert "watch-level risk does not justify messaging" in session.prompts[1]


def test_uncertain_causality_silence_is_monitor_judgment_not_protocol_override(
        monkeypatch, tmp_path):
    probe = decision(
        "HOLD", message="Run a direct control before changing production.",
        epistemic_status="causal_uncertainty", intervention_mode="discriminating_probe",
        imminent_action_anchor="Agent says it will change production from the new failing probe.",
        discrepancy="The failure may come from the test fixture or production.",
        next_safe_action="Compare the same fixture against a direct control.",
    )
    monitor, _ = build_monitor(
        monkeypatch, tmp_path, [probe, decision("SILENT", attention_mode="focused")]
    )

    first = monitor.review(packet(42))
    second = monitor.review(packet(43))

    assert "direct control" in first
    assert second == ""
    assert [bool(row["intervention_message"]) for row in monitor.decisions] == [True, False]
    assert monitor.decisions[-1]["attention"]["mode"] == "focused"
    assert monitor.pending_discriminating_probe["requested_turn"] == 42


def test_monitor_can_reassert_pending_probe_after_agent_closes_over_it(
        monkeypatch, tmp_path):
    initial = decision(
        "HOLD", message="Run the amount-format comparison before closing.",
        epistemic_status="causal_uncertainty", intervention_mode="discriminating_probe",
        imminent_action_anchor="Agent plans to close the amount obligation.",
        discrepancy="Bare integer amount semantics are unresolved.",
        exit_condition="The parser is compared on cents, decimal, and dollar fixtures.",
        next_safe_action="Run the bounded amount-format comparison.",
    )
    reassert = decision(
        "HOLD", message="The comparison remains pending; do not close over it.",
        epistemic_status="causal_uncertainty", intervention_mode="discriminating_probe",
        imminent_action_anchor="Agent again declares the root task complete without the comparison.",
        discrepancy="Bare integer amount semantics are unresolved.",
        exit_condition="The parser is compared on cents, decimal, and dollar fixtures.",
        next_safe_action="Run the same bounded amount-format comparison.",
        root_obligation_audit=root_audit(b="contested"),
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [initial, reassert])

    monitor.review(packet(42))
    result = monitor.review_completion(SimpleNamespace(response_preview="Task complete"), 43)

    assert result.decision == "CONTINUE"
    assert "comparison remains pending" in result.next_prompt
    assert monitor.pending_discriminating_probe["requested_turn"] == 42
    assert monitor.pending_discriminating_probe["reasserted_turns"] == [43]
    assert monitor.decisions[-1]["termination_decision"] == "continue_task"
    assert "control_valid" not in monitor.decisions[-1]




def test_local_attention_change_does_not_replace_root_completion_basis(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("HOLD", message="Repair local A.", discrepancy="A conflict",
                 exit_condition="A focused probe"),
        decision("RELEASE", reason="A focused probe passed"),
    ])
    original_basis = monitor.root_completion_basis

    monitor.review(packet(1))
    monitor.review(packet(2))

    assert monitor.open_episode is None
    assert monitor.root_completion_basis == original_basis






def test_completion_inspection_exhaustion_holds_and_preserves_partial_root_ledger(
        monkeypatch, tmp_path):
    ledger = root_audit(a="supported", b="unknown")
    inspections = []
    for index in range(9):
        item = {
            "action": "INSPECT",
            "reason": f"root audit batch {index}",
            "inspection": {"operation": "list_files", "path": ".", "glob": "*"},
        }
        if index == 0:
            item["root_obligation_audit"] = ledger
        inspections.append(item)
    monitor, _ = build_monitor(monkeypatch, tmp_path, inspections)

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 30)

    assert result.decision == "CONTINUE"
    assert result.reason_codes == ("M0_CONTINUE_TASK",)
    assert "monitor could not complete" in result.next_prompt
    # INSPECT is intermediate investigation, never a completion decision.
    assert monitor.decisions[-1]["control_valid"] is False
    assert "inspection budget" in monitor.decisions[-1]["reason"]












def test_m35_open_episode_history_protection_survives_restart(monkeypatch, tmp_path):
    first, _ = build_m35_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Keep the B repair aligned with the public clause.",
            discrepancy="B repair intent conflicts with the clause.",
            exit_condition="The next B action follows the clause.",
        ),
    ])
    first.review(packet(1))
    protected_start = first.open_episode_history_start
    assert protected_start == 2

    resumed_session = FakeSession([decision("SILENT", attention_mode="focused")])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )

    assert resumed.open_episode is not None
    assert resumed.open_episode_history_start == protected_start
    resumed.review(packet(2))
    assert resumed.open_episode_history_start == protected_start
    assert "Keep the B repair aligned" in json.dumps(
        resumed_session.message_batches[0], ensure_ascii=False
    )






def test_m35_restart_restores_exact_monitor_thread_after_immutable_prefix(
        monkeypatch, tmp_path):
    first_note = "Keep following the B oracle investigation after restart."
    first, first_session = build_m35_monitor(monkeypatch, tmp_path, [
        decision("SILENT", attention_mode="focused", cognitive_checkpoint={
            "continuation_note": first_note,
            "source_anchors": ["turn 1 changed B test"],
        }),
    ])
    first.review(packet(1))
    saved_tail = first.history[2:]

    resumed_session = FakeSession([decision("SILENT")])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )

    assert resumed.history[2:] == saved_tail
    assert resumed.history[:2] != []
    resumed.review(packet(2))
    restored_messages = resumed_session.message_batches[0]
    assert first_note in json.dumps(restored_messages, ensure_ascii=False)
    assert first_session.message_batches[0][0] == restored_messages[0]








def test_h4_ordinary_wake_is_navigation_only(monkeypatch, tmp_path):
    monitor, session = build_h4_monitor(monkeypatch, tmp_path, [
        decision("SILENT", attention_mode="focused"),
    ])
    current = packet(7)
    current["response_content"] = "UNIQUE_AGENT_SEMANTIC_PAYLOAD"
    current["tool_results"] = ["UNIQUE_TOOL_RESULT_PAYLOAD"]
    current["archive_delta"] = {"first_sequence": 20, "last_sequence": 23}

    monitor.review(current)

    prompt = session.prompts[0]
    assert prompt.startswith("[MONITOR WAKE]")
    assert '"archive_cursor":23' in prompt
    assert "UNIQUE_AGENT_SEMANTIC_PAYLOAD" not in prompt
    assert "UNIQUE_TOOL_RESULT_PAYLOAD" not in prompt
    assert "root_state_directory" not in prompt
    assert "cognitive_checkpoint" not in prompt
    assert "semantic_workspace_index" not in prompt
    h0 = session.message_batches[0][0]["content"][0]["text"]
    assert "TOOL LOOP" in h0
    assert "PERSISTENT NATURAL-LANGUAGE WORKSPACE" in h0
    assert "versioned history" in h0
    assert "observation_plan" in h0
    assert "wake is a navigation signal" in h0
    assert "autonomously choose" not in h0  # capability, not a forced ritual
    assert "do not perform a fixed read/write ritual" in h0
    assert "must call read_recent_delta" not in h0
    assert "Public activity advanced while you were quiet" in prompt
    assert "autonomously choose whether and how to retrieve evidence" in prompt
    recorded = monitor.decisions[-1]
    assert "cognitive_checkpoint" not in recorded
    assert "decision_focus" not in recorded
    assert "decision_value" not in recorded
    assert "observation_plan" not in recorded


def test_h4_tool_result_enters_history_once_after_active_retrieval(monkeypatch, tmp_path):
    monitor, session = build_h4_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "read the new public delta", "inspection": {
            "operation": "read_recent_delta", "limit": 5,
        }},
        decision("SILENT"),
    ])

    monitor.review(packet(4))

    assert session.prompts[0].startswith("[MONITOR WAKE]")
    assert session.prompts[1].startswith("[MONITOR CONTINUATION]")
    assert session.prompts[1].count('"new_entries"') == 1
    assert "I think the current subgoal is complete" in session.prompts[1]
    assert "CURRENT PUBLIC BOUNDARY" not in session.prompts[0]


def test_h4_consumed_large_result_becomes_retrievable_receipt_without_losing_judgment(
        monkeypatch, tmp_path):
    intervention = "Keep B contested until its public behavioral probe is observed."
    monitor, session = build_h4_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "inspect the relevant public history", "inspection": {
            "operation": "read_public_trajectory", "limit": 5,
        }},
        decision(
            "HOLD", message=intervention,
            discrepancy="B still lacks public evidence",
            exit_condition="observe the discriminating B probe",
        ),
    ])
    monitor.observe_archived_boundaries([
        {
            "archive_event_id": f"wide-{index}", "archive_sequence": index,
            "internal_turn": index, "boundary": "post_model_pre_tool",
            "response_content": f"VISIBLE_{index}_" + ("X" * 7000),
            "tool_calls": [], "tool_results": [],
        }
        for index in range(1, 6)
    ])

    assert monitor.review(packet(8)) == intervention
    assert "VISIBLE_1_" in session.prompts[1]

    history_text = json.dumps(monitor.history, ensure_ascii=False)
    assert "CONSUMED EVIDENCE RECEIPT" in history_text
    assert "VISIBLE_1_" not in history_text
    assert intervention in history_text
    assert monitor.open_episode is not None
    assert monitor.open_episode_history_start is not None

    receipt = next(
        message["content"][0]["text"] for message in monitor.history
        if message.get("role") == "user"
        and "CONSUMED EVIDENCE RECEIPT" in message["content"][0]["text"]
    )
    result_id = json.loads(receipt[receipt.find("\n{") + 1:])[
        "archived_inspections"
    ][0]["result"]["result_id"]
    archive = tmp_path / "monitor-h4" / "inspection_results" / f"{result_id}.json"
    assert "VISIBLE_1_" in archive.read_text(encoding="utf-8")
    checkpoint = json.loads(
        (tmp_path / "monitor-h4" / "monitor_checkpoint.json").read_text(encoding="utf-8")
    )
    assert "CONSUMED EVIDENCE RECEIPT" in json.dumps(checkpoint, ensure_ascii=False)
    assert "VISIBLE_1_" not in json.dumps(checkpoint["monitor_history"], ensure_ascii=False)

    resumed_session = FakeSession([decision("SILENT")])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-h4",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )
    assert "CONSUMED EVIDENCE RECEIPT" in json.dumps(resumed.history, ensure_ascii=False)
    restored = resumed._inspect_trajectory({
        "operation": "read_inspection_result", "id": result_id,
        "start_char": 0, "char_count": 12000,
    })
    assert restored["ok"] is True
    assert "VISIBLE_1_" in restored["content"]


def test_h4_consumed_result_is_elided_before_later_tool_call_in_same_review(
        monkeypatch, tmp_path):
    class HistorySession:
        max_tokens = 1024
        reasoning_effort = "high"

        def __init__(self, responses):
            self.responses = iter(responses)
            self.messages = []

        def raw_ask(self, messages):
            self.messages.append(json.loads(json.dumps(messages)))
            yield json.dumps(next(self.responses))

    session = HistorySession([
        {"action": "INSPECT", "reason": "read wide evidence", "inspection": {
            "operation": "read_public_trajectory", "limit": 5,
        }},
        {"action": "INSPECT", "reason": "read exact original clause", "inspection": {
            "operation": "read_original_task",
        }},
        decision("SILENT"),
    ])
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-progressive-f3",
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    monitor.observe_archived_boundaries([{
        "archive_event_id": f"wide-{index}", "archive_sequence": index,
        "internal_turn": index, "boundary": "post_model_pre_tool",
        "response_content": (
            f"WIDE_PROGRESSIVE_PAYLOAD_{index}_" + ("X" * 7000)
        ),
        "tool_calls": [], "tool_results": [],
    } for index in range(1, 6)])

    assert monitor.review(packet(8)) == ""
    # Call 2 consumes the wide result. Call 3 must retain only its exact
    # retrievable receipt rather than replaying the raw payload again.
    third_wire = json.dumps(session.messages[2], ensure_ascii=False)
    assert "CONSUMED EVIDENCE RECEIPT" in third_wire
    assert "WIDE_PROGRESSIVE_PAYLOAD_" not in third_wire


def test_h4_small_or_unarchived_inspection_result_remains_verbatim(monkeypatch, tmp_path):
    (tmp_path / "small.txt").write_text("SMALL_CURRENT_EVIDENCE", encoding="utf-8")
    monitor, _ = build_h4_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "read current evidence", "inspection": {
            "operation": "read_file", "path": "small.txt",
        }},
        decision("SILENT"),
    ])

    monitor.review(packet(3))

    history_text = json.dumps(monitor.history, ensure_ascii=False)
    assert "SMALL_CURRENT_EVIDENCE" in history_text
    assert "CONSUMED EVIDENCE RECEIPT" not in history_text


def test_h4_receipt_maintenance_failure_cannot_suppress_formed_intervention(
        monkeypatch, tmp_path):
    intervention = "Keep B open until the discriminating probe runs."
    monitor, _ = build_h4_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message=intervention,
            discrepancy="B closure is unsupported",
            exit_condition="observe the B probe",
        ),
    ])

    def fail_receipt_maintenance(*_args, **_kwargs):
        raise OSError("simulated receipt checkpoint failure")

    monkeypatch.setattr(
        monitor, "_replace_consumed_archived_results_with_receipts",
        fail_receipt_maintenance,
    )

    assert monitor.review(packet(10)) == intervention
    assert monitor.decisions[-1]["intervention_message"] == intervention
    assert monitor.open_episode is not None


def test_h4_consumed_history_archive_page_uses_same_exact_receipt_policy(
        monkeypatch, tmp_path):
    archive_dir = tmp_path / "monitor-h4" / "monitor_history_archives"
    archive_dir.mkdir(parents=True)
    archive_id = "compaction_0007"
    (archive_dir / f"{archive_id}.json").write_text(
        "OLD_EXACT_MONITOR_PAGE_" + ("Y" * 26000), encoding="utf-8"
    )
    monitor, session = build_h4_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "revisit exact older cognition", "inspection": {
            "operation": "read_monitor_history_archive", "id": archive_id,
            "start_char": 0, "char_count": 12000,
        }},
        decision("SILENT"),
    ])

    monitor.review(packet(9))

    assert "OLD_EXACT_MONITOR_PAGE_" in session.prompts[1]
    history_text = json.dumps(monitor.history, ensure_ascii=False)
    assert "OLD_EXACT_MONITOR_PAGE_" not in history_text
    assert "read_monitor_history_archive" in history_text
    assert archive_id in history_text


def test_h4_completion_signal_uses_same_monitor_and_active_root_retrieval(
        monkeypatch, tmp_path):
    monitor, session = build_h4_monitor(monkeypatch, tmp_path, [
        {"action": "INSPECT", "reason": "re-read immutable root task", "inspection": {
            "operation": "read_original_task",
        }},
        v2_decision(completion="allow_complete", root_obligation_audit=root_audit()),
    ])

    result = monitor.review_completion(
        SimpleNamespace(response_preview="UNIQUE_COMPLETION_CLAIM"), 12
    )

    assert result.decision == "ALLOW_COMPLETE"
    assert session.prompts[0].startswith("[ROOT COMPLETION WAKE]")
    assert "UNIQUE_COMPLETION_CLAIM" not in session.prompts[0]
    assert "last_root_obligation_audit" not in session.prompts[0]
    assert session.prompts[1].startswith("[MONITOR CONTINUATION]")
    assert "Implement A and B" in session.prompts[1]








def test_abstain_preserves_unknown_and_injects_missing_evidence(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("ABSTAIN", message="The behavior remains unknown; obtain a public discriminating observation.",
                 discrepancy="self-test may share the implementation assumption",
                 exit_condition="independently derived public probe"),
    ])
    assert "remains unknown" in monitor.review(packet())
    assert monitor.open_episode["exit_condition"] == "independently derived public probe"


def test_workspace_inspector_rejects_escape(tmp_path):
    inspector = m0.PublicWorkspaceInspector(tmp_path)
    result = inspector.execute({"operation": "read_file", "path": "../secret.txt"})
    assert result["ok"] is False
    assert "escapes public workspace" in result["error"]


















def test_h4_history_hard_bound_preserves_natural_working_state_and_archive(
        monkeypatch, tmp_path):
    monitor, session = build_h4_monitor(monkeypatch, tmp_path, [
        v2_decision(cognitive_checkpoint={
            "continuation_note": "I am tracking whether B receives behavioral evidence.",
            "source_anchors": ["turn 4 B test"],
        }),
        v2_decision(),
    ])
    monitor.history_soft_char_limit = 16000
    monitor.history.extend([{
        "role": "user", "content": [{"type": "text", "text": "X" * 40000}],
    }, {
        "role": "assistant", "content": [{"type": "text", "text": "Y" * 40000}],
    }])

    monitor.review(packet(5))

    archives = list((tmp_path / "monitor-h4" / "monitor_history_archives").glob("*.json"))
    assert len(archives) == 1
    assert "deterministic_externalization" in archives[0].read_text(encoding="utf-8")
    assert monitor._history_characters() < 50000
    assert "MONITOR CONTINUITY" in json.dumps(session.message_batches[0], ensure_ascii=False)


def test_h4_compacts_before_capturing_new_repair_history_start(monkeypatch, tmp_path):
    intervention = "Pause and reconcile B with the original contract."
    monitor, _ = build_h4_monitor(monkeypatch, tmp_path, [
        v2_decision(
            intervention=intervention, attention_mode="focused",
            discrepancy="B conflicts with its public requirement.",
            exit_condition="B has contract-faithful behavioral evidence.",
        )
    ])
    monitor.history_soft_char_limit = 16000
    monitor.history.extend([{
        "role": "user", "content": [{"type": "text", "text": "X" * 40000}],
    }, {
        "role": "assistant", "content": [{"type": "text", "text": "Y" * 40000}],
    }])

    assert intervention in monitor.review(packet(13))

    assert monitor.history_compaction_count == 1
    assert monitor.open_episode_history_start is not None
    assert 2 <= monitor.open_episode_history_start < len(monitor.history)
    assert monitor.history[0]["content"][0]["text"] != monitor.history[-1]["content"][0]["text"]


def test_intervention_without_focused_attention_is_rejected(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("HOLD", attention_mode="patrol"),
        decision("HOLD", attention_mode="patrol"),
        decision("HOLD", attention_mode="patrol"),
    ])
    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["control_valid"] is False


def test_agent_workflow_alone_cannot_authorize_hold(monkeypatch, tmp_path):
    workflow_hold = decision(
        "HOLD", message="Retry the preferred subagent workflow.",
        authority_basis="agent_workflow",
        material_task_impact="The internal SOP was not followed.",
        why_silence_is_insufficient="The SOP says so.",
    )
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        workflow_hold,
        decision("SILENT", reason="Workflow deviation is only a watch item."),
    ])

    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["intervention_message"] == ""
    assert "workflow noncompliance alone" in session.prompts[1]


def test_invalid_action_is_corrected_without_ending_task(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        {"reason": "forgot action", "notes": "x"},
        decision("SILENT", reason="corrected"),
    ])
    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["intervention_message"] == ""
    assert "Invalid or missing attention.mode" in session.prompts[1]


def test_legacy_ordinary_action_protocol_is_rejected(monkeypatch, tmp_path):
    legacy = {
        "action": "SILENT", "epistemic_status": "watch",
        "reason": "legacy response", "notes": "legacy",
    }
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        legacy, v2_decision(reason="native v2 response"),
    ])

    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["schema_version"] == "m0-monitor-decision/2"
    assert "action" not in monitor.decisions[0]
    assert "Invalid or missing attention.mode" in session.prompts[1]


def test_empty_intervention_can_choose_focused_attention_without_repair_episode(
        monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        v2_decision(attention_mode="focused", reason="watch next intent closely"),
    ])

    assert monitor.review(packet()) == ""
    assert monitor.attention_mode == "focused"
    assert monitor.open_episode is None
    assert monitor.decisions[0]["intervention_message"] == ""


def test_empty_native_attention_mode_recovers_without_extra_model_call(
        monkeypatch, tmp_path):
    response = v2_decision(attention_mode="", reason="continue focused follow-up")
    monitor, session = build_monitor(monkeypatch, tmp_path, [response])
    monitor.attention_mode = "focused"

    assert monitor.review(packet()) == ""
    assert monitor.attention_mode == "focused"
    assert len(session.prompts) == 1


def test_empty_native_attention_mode_with_intervention_enters_focus(
        monkeypatch, tmp_path):
    response = v2_decision(
        attention_mode="", intervention="Recheck the changed test oracle."
    )
    monitor, session = build_monitor(monkeypatch, tmp_path, [response])

    assert monitor.review(packet()) == "Recheck the changed test oracle."
    assert monitor.attention_mode == "focused"
    assert len(session.prompts) == 1


def test_nested_decision_object_is_accepted(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [{"decision": v2_decision()}])
    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["intervention_message"] == ""


def test_legacy_research_callback_remains_available_outside_m0(tmp_path):
    calls = []
    parent = SimpleNamespace(
        evidence_completion_kernel=None,
        verbose=False,
        task_dir=str(tmp_path),
        intervene=None,
        extrakeyinfo=None,
        obligation_ledger=None,
        research_condition=None,
        research_checkpoint_callback=lambda value: calls.append(value) or "Recheck clause B.",
        _turn_end_hooks={},
    )
    handler = GenericAgentHandler(parent, [], str(tmp_path))
    response = SimpleNamespace(content="I am done")
    tool_calls = [{"tool_name": "no_tool", "args": {}}]

    result = handler.turn_end_callback(response, tool_calls, ["done"], 1, "NEXT", None)

    assert "[RESEARCH CHECKPOINT]" in result
    assert "Recheck clause B." in result
    assert calls[0]["response_content"] == "I am done"
    assert calls[0]["boundary"] == "post_tool_pre_next_llm"


def test_m0_runtime_publishes_without_waiting_or_injecting_silence(tmp_path):
    class Runtime:
        def __init__(self): self.packets = []
        def archive_boundary(self, value): self.packets.append(value)

    runtime = Runtime()
    parent = SimpleNamespace(
        evidence_completion_kernel=None, verbose=False, task_dir=str(tmp_path),
        intervene=None, extrakeyinfo=None, obligation_ledger=None,
        research_condition=None, research_checkpoint_callback=None,
        monitor_runtime=runtime, _turn_end_hooks={},
    )
    handler = GenericAgentHandler(parent, [], str(tmp_path))

    result = handler.turn_end_callback(
        SimpleNamespace(content="continue"),
        [{"tool_name": "no_tool", "args": {}}], ["done"], 4, "NEXT", None,
    )

    assert result.startswith("NEXT")
    assert "MONITOR" not in result
    assert runtime.packets[0]["internal_turn"] == 4


def test_exit_boundary_does_not_call_online_monitor(tmp_path):
    calls = []
    parent = SimpleNamespace(
        evidence_completion_kernel=None, verbose=False, task_dir=str(tmp_path),
        intervene=None, extrakeyinfo=None, obligation_ledger=None,
        research_condition=None, research_checkpoint_callback=lambda value: calls.append(value),
        _turn_end_hooks={},
    )
    handler = GenericAgentHandler(parent, [], str(tmp_path))
    response = SimpleNamespace(content="done")
    handler.turn_end_callback(response, [{"tool_name": "no_tool", "args": {}}], ["done"], 1, "", "complete")
    assert calls == []
