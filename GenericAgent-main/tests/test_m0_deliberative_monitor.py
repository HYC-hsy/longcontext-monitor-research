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


def build_m1_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
        m1_workspace_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_m2_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.",
        workspace=tmp_path,
        config_name="fake",
        artifact_dir=tmp_path / "monitor",
        m1_workspace_enabled=True,
        m2_versioned_revision_enabled=True,
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
        m1_workspace_enabled=True,
        active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True,
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
        m1_workspace_enabled=True,
        active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True,
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
        m1_workspace_enabled=True,
        active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True,
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
        m1_workspace_enabled=True,
        active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True,
        m3_human_loop_enabled=True,
        m3_discriminative_control_enabled=True,
        m3_combined_control_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def test_m3c_is_independent_from_m3b_and_persists_one_step_inquiry(
        monkeypatch, tmp_path):
    response = v2_decision(
        attention_mode="focused",
        epistemic_status="causal_uncertainty",
        discriminative_step={
            "live_uncertainty": "Whether the failure comes from A or its test oracle.",
            "action_relevant_alternatives": "A is wrong; the oracle is wrong.",
            "next_observation": "Run the unchanged legacy A behavior against the oracle.",
            "outcome_to_action": "Repair A only if the legacy control passes.",
            "reconsider_after": "The bounded control result is public.",
        },
    )
    cleared = v2_decision(
        attention_mode="patrol",
        discriminative_step={
            "live_uncertainty": "", "action_relevant_alternatives": "",
            "next_observation": "", "outcome_to_action": "",
            "reconsider_after": "",
        },
    )
    monitor, session = build_m3c_monitor(monkeypatch, tmp_path, [response, cleared])

    monitor.review(packet())

    assert monitor.discriminative_step["next_observation"].startswith("Run the unchanged")
    checkpoint = monitor.checkpoints.load()
    assert checkpoint["m3_discriminative_control_enabled"] is True
    assert checkpoint["m3_discriminative_step"]["updated_turn"] == 1
    assert "M3-C receding-horizon discriminative control" in monitor._m3_prompt_guidance()
    assert "A direct\npublic contract conflict does not need a hypothesis exercise" in monitor._m3_prompt_guidance()

    monitor.review(packet(turn=2))
    assert monitor.discriminative_step is None
    assert monitor.checkpoints.load()["m3_discriminative_step"] is None

    authoritative = json.loads(
        (tmp_path / "monitor-m3c" / "authoritative_state.json").read_text(
            encoding="utf-8"
        )
    )
    assert authoritative["m3_discriminative_control_enabled"] is True
    assert authoritative["m3_discriminative_step"] is None

    with pytest.raises(ValueError, match="must remain independent"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            m1_workspace_enabled=True, m2_semantic_impact_enabled=True,
            m3_human_loop_enabled=True, m3_decision_value_enabled=True,
            m3_discriminative_control_enabled=True,
        )


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
    guidance = monitor._m3_prompt_guidance()
    assert "known\nconflict can coexist with uncertainty" in guidance
    monitor.adaptive_review_planning_enabled = True
    guidance = monitor._m3_prompt_guidance()
    assert "local repair may be released to patrol" in guidance


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
    assert monitor.root_obligation_audit == root_audit()
    checkpoint = monitor.checkpoints.load()
    assert checkpoint["m3d_last_closed_inquiry"]["closed_archive_sequence"] == 14
    assert checkpoint["m3_discriminative_step"] is None

    restored = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m3d",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_discriminative_control_enabled=True, m3_combined_control_enabled=True,
    )
    assert restored.discriminative_step is None
    assert restored.last_closed_inquiry["status"] == "decision_sufficient"
    assert restored.root_obligation_audit == root_audit()


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
            m1_workspace_enabled=True, m2_semantic_impact_enabled=True,
            m3_human_loop_enabled=True, m3_combined_control_enabled=True,
        )


def build_m32_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m32",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_m35_monitor(monkeypatch, tmp_path, responses):
    session = FakeSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def build_h3_monitor(monkeypatch, tmp_path, responses, *, soft_limit=16000):
    session = MixedSession(responses)
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-h3",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True, m35_history_compaction_enabled=True,
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
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True, m35_history_compaction_enabled=True,
        m35_minimal_frontstage_enabled=True,
    )
    monitor.root_obligation_audit = root_audit()
    return monitor, session


def test_m1_workspace_is_independently_disabled_in_m0(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    monitor.review(packet())

    checkpoint = json.loads((tmp_path / "monitor" / "monitor_checkpoint.json").read_text(
        encoding="utf-8"
    ))
    assert monitor.semantic_workspace is None
    assert "m1_workspace" not in checkpoint
    assert "m3_human_loop_enabled" not in checkpoint
    assert "m3_decision_focus" not in checkpoint
    assert '"decision_focus"' not in monitor._decision_schema()


def test_m2c_requires_workspace_and_is_independent(monkeypatch, tmp_path):
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))
    with pytest.raises(ValueError, match="requires the M1 workspace"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            artifact_dir=tmp_path / "missing-workspace",
            m2_semantic_impact_enabled=True,
        )
    with pytest.raises(ValueError, match="must remain independent"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            artifact_dir=tmp_path / "paired", m1_workspace_enabled=True,
            m2_versioned_revision_enabled=True, m2_semantic_impact_enabled=True,
        )


def test_m3a_requires_frozen_m2c_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))
    with pytest.raises(ValueError, match="requires the frozen M2-C"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            artifact_dir=tmp_path / "m3-without-m2c", m1_workspace_enabled=True,
            m3_human_loop_enabled=True,
        )


def test_m3a_focus_is_optional_post_hoc_memory_not_hold_gate(monkeypatch, tmp_path):
    response = decision("SILENT", decision_focus={
        "consequential_decision": "Whether the new test oracle represents clause A",
        "threatened_transition": "Promoting a self-authored test to completion evidence",
        "materiality_reversibility": "The Agent is about to run it, so another observation is safe",
        "control_rationale": "Stay silent and inspect the informative result",
        "repair_exit_condition": "No repair episode is open",
    })
    monitor, session = build_m3a_monitor(monkeypatch, tmp_path, [response])

    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["intervention_message"] == ""
    assert monitor.decisions[0]["attention"]["mode"] == "patrol"
    assert monitor.decisions[0]["decision_focus"]["consequential_decision"].startswith(
        "Whether the new test oracle"
    )
    assert monitor.decision_focus["attention_mode"] == "patrol"
    assert monitor.decision_focus["intervened"] is False
    checkpoint = json.loads((tmp_path / "monitor" / "monitor_checkpoint.json").read_text(
        encoding="utf-8"
    ))
    assert checkpoint["m3_human_loop_enabled"] is True
    assert checkpoint["m3_decision_focus"]["updated_turn"] == 1
    assert "post-hoc account" in session.prompts[0]
    assert "never require an intervention" in session.prompts[0]


def test_m3a_missing_focus_does_not_retry_or_block(monkeypatch, tmp_path):
    monitor, session = build_m3a_monitor(
        monkeypatch, tmp_path, [decision("SILENT")]
    )

    assert monitor.review(packet()) == ""
    assert len(session.prompts) == 1
    assert monitor.decisions[0]["decision_focus"] is None


def test_autonomous_wake_supplies_first_look_but_keeps_deeper_tools_optional(
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
    assert "SECRET_INTENT" in session.prompts[0]
    assert "deterministic first-look" in session.prompts[0]


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
        "root_obligation_audit": [
            {"obligation": "Implement A", "status": "supported",
             "public_evidence": ["invented evidence"]},
            {"obligation": "Demonstrate B", "status": "contested",
             "public_evidence": ["invented conflict"]},
        ],
        "cognitive_checkpoint": {
            "continuation_note": "I must preserve both explicit clauses until public evidence exists.",
            "source_anchors": ["original public task"],
        },
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

    assert result == {"status": "initialized", "obligations": 2}
    assert len(session.prompts) == 1
    assert "ORIGINAL PUBLIC TASK" in session.prompts[0]
    assert "SECRET_EXECUTION_MARKER" not in session.prompts[0]
    assert "INSPECT" not in session.prompts[0]
    assert {row["status"] for row in monitor.root_obligation_audit} == {"unknown"}
    assert all(not row["public_evidence"] for row in monitor.root_obligation_audit)
    assert [row["obligation_id"] for row in monitor.root_obligation_audit] == [
        "obligation:0000", "obligation:0001",
    ]
    assert monitor.cognitive_checkpoint["reviewed_through_turn"] == 0
    assert monitor.cognitive_checkpoint["source"] == "turn0_task_bootstrap"
    assert monitor.observation_plan["review_after_turns"] == 12
    saved = json.loads((tmp_path / "monitor-m35" / "bootstrap_state.json").read_text(
        encoding="utf-8"
    ))
    assert saved["m35_bootstrap_initialized"] is True
    assert saved["m35_cognitive_checkpoint"]["reviewed_through_archive_sequence"] == 0


def test_m35_turn0_bootstrap_is_restored_without_a_second_model_call(monkeypatch, tmp_path):
    response = {
        "root_obligation_audit": [
            {"obligation": "Implement A", "status": "unknown", "public_evidence": []},
            {"obligation": "Demonstrate B", "status": "unknown", "public_evidence": []},
        ],
        "cognitive_checkpoint": {
            "continuation_note": "Preserve both clauses and await public evidence.",
            "source_anchors": ["original public task"],
        },
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
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True,
    )

    assert restored.bootstrap_task_state() == {"status": "restored", "obligations": 2}
    assert restored_session.prompts == []
    assert restored.cognitive_checkpoint["continuation_note"].startswith("Preserve both")
    assert [row["obligation_id"] for row in restored.root_obligation_audit] == [
        "obligation:0000", "obligation:0001",
    ]


def test_m3b_requires_m3a_parent(monkeypatch, tmp_path):
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))
    with pytest.raises(ValueError, match="requires the M3-A"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            artifact_dir=tmp_path / "m3b-without-m3a",
            m1_workspace_enabled=True, m2_semantic_impact_enabled=True,
            m3_decision_value_enabled=True,
        )


def test_m3b_value_record_is_optional_and_does_not_force_hold(monkeypatch, tmp_path):
    response = decision("SILENT", decision_value={
        "live_decision": "Whether another queue probe would change the implementation action",
        "distinguishing_outcomes": "Queued delivery works or propagation is genuinely absent",
        "action_sensitivity": "Only the latter warrants a production edit",
        "task_impact_and_cost": "One bounded probe avoids a risky edit at small delay",
        "exit_or_switch_condition": "Resume implementation after the queue result",
    })
    monitor, session = build_m3b_monitor(monkeypatch, tmp_path, [response])

    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["intervention_message"] == ""
    assert monitor.decisions[0]["decision_value"]["action_sensitivity"].startswith(
        "Only the latter"
    )
    checkpoint = json.loads((tmp_path / "monitor" / "monitor_checkpoint.json").read_text(
        encoding="utf-8"
    ))
    assert checkpoint["m3_decision_value_enabled"] is True
    assert checkpoint["m3_decision_value"]["updated_turn"] == 1
    assert "If no plausible result would change" in session.prompts[0]
    assert "not numeric scores" in session.prompts[0]


def test_m32_monitor_authors_and_checkpoints_its_next_semantic_patrol(monkeypatch, tmp_path):
    response = decision("SILENT", observation_plan={
        "review_after_turns": 7,
        "focus": "Whether generated tests preserve both explicit obligations",
        "expected_progress": "A first behaviorally discriminating test batch",
        "reason": "The Agent is making safe progress, but its tests will guide implementation",
    })
    monitor, session = build_m32_monitor(monkeypatch, tmp_path, [response])

    assert monitor.review(packet()) == ""
    assert monitor.observation_plan["review_after_turns"] == 7
    assert monitor.observation_plan["focus"].startswith("Whether generated tests")
    assert monitor.decisions[0]["observation_plan"]["source"] == "monitor"
    checkpoint = json.loads(
        (tmp_path / "monitor-m32" / "monitor_checkpoint.json").read_text(encoding="utf-8")
    )
    assert checkpoint["m32_adaptive_review_planning_enabled"] is True
    assert checkpoint["m32_observation_plan"]["review_after_turns"] == 7
    assert "estimate in observation_plan" in session.prompts[0]
    assert "never interprets them" in session.prompts[0]


def test_m32_missing_plan_uses_recovery_default_without_forcing_hold(monkeypatch, tmp_path):
    monitor, _ = build_m32_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    assert monitor.review(packet()) == ""
    assert monitor.observation_plan["review_after_turns"] == 20
    assert monitor.observation_plan["carried_forward"] is True


def test_m3b_missing_value_record_remains_valid_and_permissive(monkeypatch, tmp_path):
    monitor, session = build_m3b_monitor(
        monkeypatch, tmp_path, [decision("SILENT")]
    )

    assert monitor.review(packet()) == ""
    assert len(session.prompts) == 1
    assert monitor.decisions[0]["decision_value"] is None


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


def test_m2c_prompt_preserves_monitor_judgment_and_forbids_completion_authority(
        monkeypatch, tmp_path):
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A.", workspace=tmp_path, config_name="fake",
        artifact_dir=tmp_path / "monitor-c", m1_workspace_enabled=True,
        m2_semantic_impact_enabled=True,
    )
    guidance = monitor._m1_prompt_guidance()
    schema = monitor._decision_schema()
    assert "runtime validates identity, provenance, and local relation scope" in guidance
    assert "does not validate semantic" in guidance
    assert "can never establish completion" in guidance
    assert '"semantic_impacts"' in schema
    assert not (tmp_path / "monitor" / "m1_workspace.json").exists()


def test_m1_final_decision_updates_workspace_without_forcing_hold(monkeypatch, tmp_path):
    response = decision("SILENT", workspace_delta={
        "upsert": [{
            "id": "intent:edit-a", "role": "local_intent",
            "summary": "Edit A based on the observed failing branch",
            "state": "active", "source_anchors": ["turn:1 response"],
            "root_links": ["root:public-task"],
        }],
        "deactivate": [],
        "relations": [{
            "source": "intent:edit-a", "relation": "contributes_to",
            "target": "root:public-task", "summary": "Current local work serves A",
        }],
    })
    monitor, session = build_m1_monitor(monkeypatch, tmp_path, [response])

    assert monitor.review(packet()) == ""
    saved = json.loads((tmp_path / "monitor" / "m1_workspace.json").read_text(
        encoding="utf-8"
    ))
    assert any(row["id"] == "intent:edit-a" for row in saved["objects"])
    assert monitor.decisions[0]["workspace_update_result"]["upserted"] == 1
    assert '"m1_semantic_workspace"' in session.prompts[0]


def test_m1_read_only_watch_does_not_persist_semantic_churn(monkeypatch, tmp_path):
    delta = {"upsert": [{
        "id": "question:transient", "role": "open_question",
        "summary": "A read-only search is still in progress",
        "source_anchors": ["turn:1"], "root_links": ["root:public-task"],
    }], "deactivate": [], "relations": []}
    monitor, _ = build_m1_monitor(
        monkeypatch, tmp_path, [decision("SILENT", workspace_delta=delta)]
    )
    current = packet()
    current["tool_calls"] = [{"tool_name": "file_read", "args": {"path": "x.py"}}]

    assert monitor.review(current) == ""
    assert "question:transient" not in {
        row["id"] for row in monitor.semantic_workspace.view()["objects"]
    }
    assert monitor.decisions[-1]["workspace_update_result"]["reason"] == "no_semantic_event"


def test_m1_archive_wake_persists_monitor_authored_semantic_delta(monkeypatch, tmp_path):
    """Production wake packets carry cursors, not task-side semantic tool calls."""
    delta = {"upsert": [{
        "id": "evidence:archive-7", "role": "public_evidence",
        "summary": "The archived test result contradicts the prior assumption.",
        "state": "observed", "source_anchors": ["archive_sequence:7"],
        "root_links": ["obligation:0000"],
    }], "deactivate": [], "relations": []}
    monitor, _ = build_m1_monitor(
        monkeypatch, tmp_path, [decision("SILENT", workspace_delta=delta)]
    )
    current = {
        "archive_wake_only": True,
        "boundary": "autonomous_archive_observation",
        "internal_turn": 4,
        "archive_delta": {"first_sequence": 6, "last_sequence": 7},
        "response_content": "", "tool_calls": [], "tool_results": [],
    }

    assert monitor.review(current) == ""
    assert monitor.semantic_workspace.get_object("evidence:archive-7")["ok"] is True
    assert monitor.decisions[-1]["workspace_update_result"]["upserted"] == 1


def test_m1_root_audit_rephrasing_cannot_move_evidence_by_position(
        monkeypatch, tmp_path):
    paraphrased = [
        {"obligation": "A appears complete now", "status": "supported",
         "public_evidence": ["turn 4"]},
        {"obligation": "B remains uncertain", "status": "contested",
         "public_evidence": ["turn 5"]},
    ]
    monitor, _ = build_m1_monitor(
        monkeypatch, tmp_path, [
            decision("SILENT", root_obligation_audit=paraphrased),
            decision("SILENT"),
        ]
    )

    monitor.review(packet())

    assert [row["obligation"] for row in monitor.root_obligation_audit] == [
        "Implement A", "Implement B",
    ]
    assert monitor.root_obligation_audit == root_audit()
    assert monitor.semantic_workspace.metrics()["root_obligations"] == 2


def test_m1_stable_ids_require_exact_contract_binding_before_state_update(
        monkeypatch, tmp_path):
    revised = [
        {"obligation_id": "obligation:0000", "obligation": "paraphrased A",
         "status": "supported", "public_evidence": ["turn 4"]},
        {"obligation_id": "obligation:0001", "obligation": "paraphrased B",
         "status": "contested", "public_evidence": ["turn 5"]},
    ]
    monitor, session = build_m1_monitor(
        monkeypatch, tmp_path, [
            decision("SILENT", root_obligation_audit=revised),
            decision("SILENT"),
        ]
    )

    monitor.review(packet())

    assert [row["obligation"] for row in monitor.root_obligation_audit] == [
        "Implement A", "Implement B",
    ]
    assert monitor.root_obligation_audit == root_audit()
    assert "is bound to" in session.prompts[1]


def test_root_audit_scale_change_never_uses_positional_evidence_fallback(
        monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    original = [{
        "obligation_id": f"obligation:{index:04d}",
        "obligation": f"Original requirement {index}",
        "status": "unknown", "public_evidence": [],
    } for index in range(63)]
    monitor.root_obligation_audit = original
    paraphrased = [{
        "obligation": f"Rephrased or shifted requirement {index}",
        "status": "supported", "public_evidence": [f"wrong evidence {index}"],
    } for index in range(78)]

    reconciled = monitor._reconcile_root_audit(paraphrased)

    assert reconciled == original
    assert all(not row["public_evidence"] for row in reconciled)


def test_root_audit_reordering_with_stable_ids_updates_correct_rows(
        monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    captured = [
        {"obligation_id": "obligation:0001", "obligation": "Implement B",
         "status": "contested", "public_evidence": ["B failure"]},
        {"obligation_id": "obligation:0000", "obligation": "Implement A",
         "status": "supported", "public_evidence": ["A test"]},
    ]

    reconciled = monitor._reconcile_root_audit(captured)

    assert [row["obligation"] for row in reconciled] == ["Implement A", "Implement B"]
    assert reconciled[0]["public_evidence"] == ["A test"]
    assert reconciled[1]["public_evidence"] == ["B failure"]


def test_root_audit_swapped_id_text_binding_is_rejected_without_evidence_transfer(
        monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    swapped = [
        {"obligation_id": "obligation:0000", "obligation": "Implement B",
         "status": "supported", "public_evidence": ["B evidence"]},
        {"obligation_id": "obligation:0001", "obligation": "Implement A",
         "status": "contested", "public_evidence": ["A evidence"]},
    ]

    candidate, errors = monitor._prepare_root_audit_candidate(swapped)

    assert errors
    assert candidate == root_audit()
    assert monitor.root_obligation_audit == root_audit()


def test_new_root_obligation_id_is_runtime_assigned(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    captured = [*root_audit(), {
        "obligation": "Implement C", "status": "unknown", "public_evidence": [],
    }]

    candidate, errors = monitor._prepare_root_audit_candidate(captured)

    assert errors == []
    assert candidate[-1]["obligation_id"] == "obligation:0002"


def test_model_supplied_new_root_id_is_rejected(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    captured = [*root_audit(), {
        "obligation_id": "custom-new-id", "obligation": "Implement C",
        "status": "unknown", "public_evidence": [],
    }]

    candidate, errors = monitor._prepare_root_audit_candidate(captured)

    assert candidate == root_audit()
    assert "unknown model-supplied obligation_id custom-new-id" in errors


def test_invalid_final_decision_cannot_commit_valid_root_candidate(monkeypatch, tmp_path):
    revised = root_audit(a="contested", b="unknown")
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", attention_mode="invalid", root_obligation_audit=revised),
        decision("SILENT"),
    ])

    monitor.review(packet())

    assert len(session.prompts) == 2
    assert monitor.root_obligation_audit == root_audit()


def test_workspace_failure_rolls_back_root_candidate_and_decision(monkeypatch, tmp_path):
    revised = root_audit(a="contested", b="unknown")
    monitor, _ = build_m1_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=revised),
    ])
    original_decisions = list(monitor.decisions)

    def fail_root_sync(*_args, **_kwargs):
        raise OSError("simulated workspace persistence failure")

    monkeypatch.setattr(
        monitor.semantic_workspace, "sync_root_obligations", fail_root_sync
    )

    with pytest.raises(OSError, match="simulated workspace"):
        monitor.review(packet(4))

    assert monitor.root_obligation_audit == root_audit()
    assert monitor.decisions == original_decisions


def test_completion_retries_when_snapshot_drops_stable_obligation_ids(
        monkeypatch, tmp_path):
    paraphrased = [
        {"obligation": "A is done", "status": "supported",
         "public_evidence": ["A claim"]},
        {"obligation": "B is done", "status": "supported",
         "public_evidence": ["B claim"]},
    ]
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        v2_decision(completion="allow_complete", root_obligation_audit=paraphrased),
        v2_decision(completion="allow_complete", root_obligation_audit=root_audit()),
    ])
    completion_packet = packet(9)
    completion_packet["boundary"] = "completion_proposal"

    assert monitor.review(completion_packet) == ""
    assert len(session.prompts) == 2
    assert "stable runtime identity" in session.prompts[1]
    assert monitor.root_obligation_audit == root_audit()


def test_m1_routine_prompt_uses_bounded_view_not_full_workspace(monkeypatch, tmp_path):
    monitor, session = build_m1_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    monitor.semantic_workspace.sync_root_obligations(root_audit(), 1, 1)
    for index in range(60):
        monitor.semantic_workspace.apply_delta({"upsert": [{
            "id": f"evidence:{index}", "role": "public_evidence",
            "summary": f"unique-evidence-{index}", "source_anchors": [f"turn:{index}"],
            "root_links": ["obligation:0000"],
        }], "deactivate": [], "relations": []}, turn=index + 2, decision_index=index + 2)

    monitor.review(packet(70))

    assert "unique-evidence-59" in session.prompts[0]
    assert "unique-evidence-0" not in session.prompts[0]
    checkpoint = json.loads((tmp_path / "monitor" / "monitor_checkpoint.json").read_text(
        encoding="utf-8"
    ))
    assert "m1_workspace_metrics" in checkpoint
    assert "m1_workspace" not in checkpoint


def test_m1_monitor_can_reconstruct_from_semantic_workspace(monkeypatch, tmp_path):
    first, _ = build_m1_monitor(monkeypatch, tmp_path, [decision(
        "SILENT", workspace_delta={
            "upsert": [{"id": "hypothesis:one", "role": "causal_hypothesis",
                        "summary": "A parser branch is suspect", "source_anchors": ["turn:1"],
                        "root_links": ["root:public-task"]}],
            "deactivate": [], "relations": [],
        },
    )])
    first.review(packet(1))

    second_session = FakeSession([
        {"action": "INSPECT", "reason": "reconstruct hypothesis", "inspection": {
            "operation": "search_semantic_workspace", "pattern": "parser",
        }},
        decision("SILENT"),
    ])
    monkeypatch.setattr(m0, "resolve_session", lambda _: second_session)
    restored = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor",
        m1_workspace_enabled=True,
    )
    restored.review(packet(2))

    assert '"matched": 1' in second_session.prompts[1]
    assert "A parser branch is suspect" in second_session.prompts[1]


def test_m2_monitor_preserves_revision_without_changing_decision_protocol(
        monkeypatch, tmp_path):
    initial = decision("SILENT", workspace_delta={
        "upsert": [{"id": "evidence:a", "role": "public_evidence",
                    "summary": "A passed on implementation v1", "state": "supported",
                    "source_anchors": ["turn:1:test", "code:a@v1"],
                    "root_links": ["obligation:0000"]}],
        "deactivate": [], "relations": [],
    })
    revised = decision("SILENT", workspace_delta={
        "upsert": [{"id": "evidence:a", "role": "public_evidence",
                    "summary": "A changed; prior test scope is stale", "state": "unknown",
                    "source_anchors": ["turn:2:patch", "code:a@v2"],
                    "root_links": ["obligation:0000"]}],
        "deactivate": [], "relations": [],
    })
    monitor, session = build_m2_monitor(monkeypatch, tmp_path, [initial, revised])

    assert monitor.review(packet(1)) == ""
    assert monitor.review(packet(2)) == ""
    evidence = monitor.semantic_workspace.get_object("evidence:a")
    assert evidence["object"]["object_version"] == 2
    assert evidence["revision_history"][0]["previous"]["state"] == "supported"
    assert "do not\nmanufacture updates merely to populate history" in session.prompts[0]
    assert all(not row["intervention_message"] for row in monitor.decisions)


def test_m2_accepted_impact_reopens_authoritative_root_audit(monkeypatch, tmp_path):
    delta = {
        "upsert": [{
            "id": "evidence:conflict-a", "role": "public_evidence",
            "summary": "A later public run contradicts support for A.",
            "state": "observed", "source_anchors": ["archive_sequence:9"],
            "root_links": ["obligation:0000"],
        }],
        "deactivate": [],
        "relations": [{
            "source": "evidence:conflict-a", "relation": "conflicts_with",
            "target": "obligation:0000", "summary": "The later run bears on A.",
        }],
        "semantic_impacts": [{
            "target_id": "obligation:0000", "cause_id": "evidence:conflict-a",
            "effect": "contest", "reason": "The former warrant no longer holds.",
            "public_anchors": ["archive_sequence:9"],
        }],
    }
    monitor, _ = build_m3a_monitor(
        monkeypatch, tmp_path, [decision("SILENT", workspace_delta=delta)]
    )
    current = {
        "archive_wake_only": True,
        "boundary": "autonomous_archive_observation",
        "internal_turn": 5,
        "archive_delta": {"first_sequence": 8, "last_sequence": 9},
        "response_content": "", "tool_calls": [], "tool_results": [],
    }

    monitor.review(current)

    assert monitor.root_obligation_audit[0]["status"] == "contested"
    assert "semantic_reopen:evidence:conflict-a" in monitor.root_obligation_audit[0][
        "public_evidence"
    ]
    root = monitor.semantic_workspace.get_object("obligation:0000")["object"]
    assert root["state"] == "contested"


def test_m2_reopen_records_proposal_and_committed_authority_separately(
        monkeypatch, tmp_path):
    delta = {
        "upsert": [{
            "id": "evidence:late-conflict", "role": "public_evidence",
            "summary": "A later public result conflicts with A.",
            "state": "observed", "source_anchors": ["archive_sequence:12"],
            "root_links": ["obligation:0000"],
        }],
        "deactivate": [], "relations": [],
        "semantic_impacts": [{
            "target_id": "obligation:0000", "cause_id": "evidence:late-conflict",
            "effect": "contest", "reason": "The former support is stale.",
            "public_anchors": ["archive_sequence:12"],
        }],
    }
    monitor, _ = build_m3a_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=root_audit(), workspace_delta=delta)
    ])

    monitor.review(packet(6))

    recorded = monitor.decisions[-1]
    assert recorded["proposed_root_obligation_audit"][0]["status"] == "supported"
    assert recorded["root_obligation_audit"][0]["status"] == "contested"
    checkpoint = json.loads(
        (tmp_path / "monitor" / "monitor_checkpoint.json").read_text(encoding="utf-8")
    )
    assert checkpoint["root_obligation_audit"][0]["status"] == "contested"


def test_m2_requires_m1_workspace(monkeypatch, tmp_path):
    session = FakeSession([])
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    with pytest.raises(ValueError, match="requires the M1 workspace"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            artifact_dir=tmp_path / "monitor", m2_versioned_revision_enabled=True,
        )


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


def test_h3_archives_exact_history_then_preserves_two_raw_wakes(monkeypatch, tmp_path):
    monitor, _ = build_h3_monitor(monkeypatch, tmp_path, [
        decision("SILENT", notes="old patrol cognition"),
        decision("SILENT", notes="recent patrol one"),
        decision("SILENT", notes="recent patrol two"),
        "I established an older public observation, but it remains revisable at source turn 1.",
    ])

    monitor.review(packet(1))
    monitor.review(packet(2))
    monitor.review(packet(3))

    archives = list((tmp_path / "monitor-h3" / "monitor_history_archives").glob("*.json"))
    assert len(archives) == 1
    archived = json.loads(archives[0].read_text(encoding="utf-8"))
    assert archived["status"] == "compacted"
    cut = archived["compacted_before_message"]
    protected_tail = archived["full_history"][cut:]
    assert monitor.history[-len(protected_tail):] == protected_tail
    assert "I established an older public observation" in monitor.history[2]["content"][0]["text"]
    assert monitor.history_review_starts[0] == 4
    assert monitor._history_characters() < archived["history_characters"]
    listing = monitor._inspect_trajectory({
        "operation": "list_monitor_history_archives"
    })
    assert listing["archives"][0]["id"] == archives[0].stem
    page = monitor._inspect_trajectory({
        "operation": "read_monitor_history_archive", "id": archives[0].stem,
    })
    recovered = [page["content"]]
    while page["truncated"]:
        page = monitor._inspect_trajectory(page["continuation"])
        recovered.append(page["content"])
    assert "".join(recovered) == archives[0].read_text(encoding="utf-8")


def test_h3_summary_failure_keeps_exact_live_history(monkeypatch, tmp_path):
    monitor, _ = build_h3_monitor(monkeypatch, tmp_path, [
        decision("SILENT"), decision("SILENT"), decision("SILENT"),
        "!!!Error: compaction provider unavailable",
    ])

    monitor.review(packet(1))
    monitor.review(packet(2))
    monitor.review(packet(3))

    archive = next(
        (tmp_path / "monitor-h3" / "monitor_history_archives").glob("*.json")
    )
    saved = json.loads(archive.read_text(encoding="utf-8"))
    assert saved["status"] == "summary_failed"
    assert monitor.history == saved["full_history"]


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


def test_h3_does_not_compact_before_returning_intervention(monkeypatch, tmp_path):
    monitor, session = build_h3_monitor(monkeypatch, tmp_path, [
        decision("SILENT", notes="old closed patrol"),
        decision("SILENT", notes="second closed patrol"),
        decision(
            "HOLD", message="Correct B before the next task-model turn.",
            discrepancy="B now conflicts with the public task.",
            exit_condition="B intent is aligned with the public task.",
        ),
    ], soft_limit=1)
    # Keep the first two reviews below the synthetic threshold so the third
    # review is the first eligible compaction point.
    monitor.history_soft_char_limit = 10**9
    monitor.review(packet(1))
    monitor.review(packet(2))
    monitor.history_soft_char_limit = 1

    message = monitor.review(packet(3))

    assert "Correct B" in message
    assert len(session.responses) == 0
    assert not (tmp_path / "monitor-h3" / "monitor_history_archives").exists()


def test_h3_does_not_compact_on_root_completion_boundary(monkeypatch, tmp_path):
    monitor, session = build_h3_monitor(monkeypatch, tmp_path, [
        decision("SILENT", notes="old closed patrol"),
        decision("SILENT", notes="second closed patrol"),
        v2_decision(completion="allow_complete", root_obligation_audit=root_audit()),
    ], soft_limit=1)
    monitor.history_soft_char_limit = 10**9
    monitor.review(packet(1))
    monitor.review(packet(2))
    monitor.history_soft_char_limit = 1

    result = monitor.review_completion(
        SimpleNamespace(response_preview="A and B are complete"), 3
    )

    assert result.decision == "ALLOW_COMPLETE"
    assert len(session.responses) == 0
    assert not (tmp_path / "monitor-h3" / "monitor_history_archives").exists()


def test_h3_compacted_history_and_review_indexes_survive_restart(monkeypatch, tmp_path):
    monitor, _ = build_h3_monitor(monkeypatch, tmp_path, [
        decision("SILENT"), decision("SILENT"), decision("SILENT"),
        "Older closed patrol was compacted with public anchors.",
    ])
    monitor.review(packet(1)); monitor.review(packet(2)); monitor.review(packet(3))
    expected_history = monitor.history
    expected_starts = monitor.history_review_starts

    resumed_session = MixedSession([])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-h3",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True, m35_history_compaction_enabled=True,
        history_soft_char_limit=16000, history_target_characters=12000,
    )

    assert resumed.history == expected_history
    assert resumed.history_review_starts == expected_starts
    assert resumed.history_compaction_count == 1


def test_decision_and_state_archives_are_atomic_utf8_json(monkeypatch, tmp_path):
    special = "引号“契约” — café\n第二行"
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", notes=special, unresolved_unknown="路径 /tmp/未知"),
    ])

    monitor.review(packet())

    artifact_dir = tmp_path / "monitor"
    decision_path = artifact_dir / "decision_0001.json"
    state_path = artifact_dir / "authoritative_state.json"
    saved = json.loads(decision_path.read_text(encoding="utf-8"))
    authoritative = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["notes"] == special
    assert authoritative["schema_version"] == "m0-authoritative-state/2"
    assert not list(artifact_dir.glob("*.tmp"))


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


def test_recent_trajectory_is_an_optional_observation_ablation(monkeypatch, tmp_path):
    session = FakeSession([
        decision("SILENT", root_obligation_audit=root_audit()),
        decision("SILENT"),
    ])
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task="Implement A and B.", workspace=tmp_path, config_name="fake",
        artifact_dir=tmp_path / "monitor", recent_trajectory_turns=2,
    )
    monitor.review(packet(1))
    monitor.review(packet(2))

    assert '"recent_public_trajectory"' in session.prompts[0]
    assert '"internal_turn": 1' in session.prompts[1]
    assert '"internal_turn": 2' in session.prompts[1]


def test_monitor_can_actively_query_complete_public_trajectory(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", notes="first observed"),
        {"action": "INSPECT", "reason": "revisit prior intent", "inspection": {
            "operation": "search_public_trajectory", "pattern": "subgoal", "limit": 10,
        }},
        decision("SILENT", notes="history checked"),
    ])
    monitor.review(packet(1))
    monitor.review(packet(2))

    assert '"operation": "search_public_trajectory"' in session.prompts[2]
    assert '"matched": 2' in session.prompts[2]
    assert '"internal_turn": 1' in session.prompts[2]
    assert '"internal_turn": 2' in session.prompts[2]


def test_monitor_can_query_its_prior_decisions(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", notes="remember first boundary"),
        {"action": "INSPECT", "reason": "revisit my judgment", "inspection": {
            "operation": "read_monitor_decisions", "start_turn": 1, "end_turn": 1,
        }},
        decision("SILENT"),
    ])
    monitor.review(packet(1))
    monitor.review(packet(2))

    assert '"notes": "remember first boundary"' in session.prompts[2]
    assert '"intervention_message": ""' in session.prompts[2]


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


def test_open_episode_can_be_actively_revisited_without_closing_on_silence(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("HOLD", message="Recheck the oracle.", discrepancy="oracle unsupported",
                 exit_condition="validated probe"),
        decision("SILENT", attention_mode="focused", notes="agent is investigating"),
        {"action": "INSPECT", "reason": "review uptake", "inspection": {
            "operation": "read_repair_episode", "limit": 10,
        }},
        decision("SILENT", attention_mode="focused", notes="repair continues"),
    ])
    monitor.review(packet(1))
    monitor.review(packet(2))
    assert monitor.attention_mode == "focused"
    assert monitor.open_episode is not None
    monitor.review(packet(3))

    assert '"original_discrepancy": "oracle unsupported"' in session.prompts[3]
    assert '"internal_turn": 1' in session.prompts[3]
    assert '"internal_turn": 3' in session.prompts[3]


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


def test_test_artifact_and_causal_intent_are_attention_signals():
    value = packet(4)
    value["response_content"] = "The test failed, therefore I will change production."
    value["tool_calls"] = [{"tool_name": "file_write", "args": {"path": "tests/test_api.py"}}]
    signals = m0.M0DeliberativeMonitor._attention_signals(value)
    assert "test_artifact_boundary" in signals
    assert "public_causal_or_change_intent" in signals


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


def test_completion_hold_continues_task_with_full_public_response(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Do not finish until B has behavioral evidence.",
            discrepancy="B is unsupported", exit_condition="run a B probe",
            root_obligation_audit=root_audit(b="unknown"),
        ),
    ])
    proposal = SimpleNamespace(response_preview="short preview")

    result = monitor.review_completion(
        proposal, 23, {}, "Full completion claim: A is tested, B is assumed done."
    )

    assert result.decision == "CONTINUE"
    assert "behavioral evidence" in result.next_prompt
    assert "Full completion claim" in session.prompts[0]
    assert monitor.open_episode["discrepancy"] == "B is unsupported"


def test_completion_silence_allows_task_to_finish(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=root_audit())
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 24)

    assert result.decision == "ALLOW_COMPLETE"
    assert result.reason_codes == ("M0_ALLOW_COMPLETE",)
    assert "Agent requesting permission to stop" in session.prompts[0]
    assert "allow_complete approves ROOT-TASK termination" in session.prompts[0]


def test_completion_prompt_distinguishes_premature_clarification_from_real_ambiguity(
    monkeypatch, tmp_path,
):
    hold = decision(
        "HOLD",
        message="Begin the concrete work already requested.",
        discrepancy="The executable task was not started.",
        authority_basis="user_contract",
        material_task_impact="Stopping now leaves the requested work undone.",
        why_silence_is_insufficient="Silence at this boundary permits termination.",
        root_obligation_audit=root_audit(a="unknown", b="unknown"),
    )
    monitor, session = build_monitor(monkeypatch, tmp_path, [hold])

    result = monitor.review_completion(
        SimpleNamespace(response_preview="What would you like me to do?"), 2,
    )

    assert result.decision == "CONTINUE"
    assert "unnecessary clarification request" in session.prompts[0]
    assert "genuinely absent choice" in session.prompts[0]
    assert "roadmap" not in session.prompts[0].lower()


def test_completion_environment_blocked_unknown_must_release(monkeypatch, tmp_path):
    blocked = decision(
        "ABSTAIN",
        message="Obtain runtime evidence.",
        evidence_availability="environment_blocked",
        next_safe_action="",
        discrepancy="Runtime behavior is unobserved.",
        root_obligation_audit=root_audit(b="unknown"),
    )
    release = decision(
        "RELEASE",
        reason="No safe public action can produce stronger evidence.",
        evidence_availability="environment_blocked",
        unresolved_unknown="Runtime behavior remains unverified because a required dependency is absent.",
        notes="Source conflict resolved; runtime evidence remains UNKNOWN.",
        root_obligation_audit=root_audit(b="unknown"),
    )
    monitor, session = build_monitor(monkeypatch, tmp_path, [blocked, release])

    result = monitor.review_completion(
        SimpleNamespace(response_preview="done"), 25, {},
        "Source is repaired; runtime verification is UNKNOWN because the dependency is absent.",
    )

    assert result.decision == "ALLOW_COMPLETE"
    assert result.reason_codes == ("M0_ALLOW_COMPLETE",)
    assert monitor.decisions[-1]["unresolved_unknown"].startswith("Runtime behavior")
    assert monitor.open_episode is None
    assert "allow_complete with UNKNOWN" in session.prompts[1]


def test_completion_preserves_unknown_without_forcing_more_available_checks(
        monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision(
            "RELEASE",
            reason="No concrete discrepancy remains; another check would be speculative.",
            evidence_availability="not_applicable",
            unresolved_unknown="B has no independent proof beyond the public implementation evidence.",
            root_obligation_audit=root_audit(b="unknown"),
        ),
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 25)

    assert result.decision == "ALLOW_COMPLETE"
    assert monitor.root_obligation_audit[1]["status"] == "unknown"
    assert monitor.decisions[-1]["unresolved_unknown"].startswith("B has no independent")


def test_root_unknown_can_record_deliberative_disposition_without_becoming_gate(
        monkeypatch, tmp_path):
    audit = root_audit(b="unknown")
    audit[1].update({
        "uncertainty_disposition": "residual_uncertainty",
        "resolution_owner": "preserve_unknown",
        "plausible_counterexample": "No trajectory-grounded nearby failure is public.",
        "bounded_probe": "",
    })
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision(
            "RELEASE",
            unresolved_unknown="B remains a residual uncertainty.",
            root_obligation_audit=audit,
        ),
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 25)

    assert result.decision == "ALLOW_COMPLETE"
    assert monitor.root_obligation_audit[1]["uncertainty_disposition"] == "residual_uncertainty"
    assert monitor.root_obligation_audit[1]["resolution_owner"] == "preserve_unknown"
    assert "bounded_probe" not in monitor.root_obligation_audit[1]


def test_prompt_activates_counterexample_grounded_information_value(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=root_audit())
    ])
    base_prompt = monitor.history[0]["content"][0]["text"]

    assert "material evidence debt" in base_prompt
    assert "residual uncertainty" in base_prompt
    assert "plausible nearby wrong implementation" in base_prompt
    assert "one causally coherent bounded probe" in base_prompt
    monitor.review_completion(SimpleNamespace(response_preview="done"), 25)
    assert "do not maximize clause coverage" in session.prompts[0]
    assert "resolution_owner" in session.prompts[0]
    assert "comprehensive root checker" in session.prompts[0]
    assert "making that auxiliary checker perfect" in session.prompts[0]
    assert "not a checklist" in session.prompts[0]
    assert "protocol gate" in session.prompts[0]


def test_completion_still_rejects_release_with_material_contested_clause(
        monkeypatch, tmp_path):
    contested = root_audit()
    contested[1]["status"] = "contested"
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision(
            "RELEASE",
            unresolved_unknown="B remains uncertain.",
            root_obligation_audit=contested,
        ),
        decision(
            "HOLD",
            message="Repair the observed B conflict.",
            discrepancy="B contradicts the original clause.",
            exit_condition="A direct B observation no longer conflicts.",
            root_obligation_audit=contested,
        ),
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 25)

    assert result.decision == "CONTINUE"
    assert "material contested obligation" in session.prompts[1]


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


def test_completion_rejects_release_without_root_audit(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("RELEASE", reason="the existing suite passes", root_obligation_audit=[]),
        decision(
            "HOLD", message="B still has no public coverage.",
            discrepancy="root obligation B was omitted",
            exit_condition="implement and probe B",
            root_obligation_audit=root_audit(b="unknown"),
        ),
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 27)

    assert result.decision == "CONTINUE"
    assert monitor.root_obligation_audit[1]["status"] == "unknown"
    assert "requires a non-empty root_obligation_audit" in session.prompts[1]


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

    assert "M0 AUTHORITATIVE RECOVERY PACKAGE" in message
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


def test_prompt_exposes_deterministic_evidence_hazards(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    risky = packet(40)
    risky["response_content"] = "Final verification: go test ./... | tail -20"
    risky["tool_results"] = ["[no tests to run]\nFAIL\nexit code 0"]

    monitor.review(risky)

    prompt = session.prompts[0]
    assert "masked_test_exit_status" in prompt
    assert "no_test_selected" in prompt
    assert "content_status_conflict" in prompt


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


def test_completion_protocol_failure_cannot_silently_finish_root_task(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("RELEASE"), decision("RELEASE"), decision("RELEASE")
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 29)

    assert result.decision == "CONTINUE"
    assert result.reason_codes == ("M0_CONTINUE_TASK",)
    assert "monitor could not complete its internal root-task audit" in result.next_prompt
    assert monitor.decisions[-1]["control_valid"] is False
    assert monitor.attention_mode == "focused"
    assert monitor.open_episode is not None


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
    assert monitor.root_obligation_audit == root_audit()


def test_noncompletion_decision_persists_root_ledger_without_opening_unknown_episode(
        monkeypatch, tmp_path):
    ledger = root_audit(a="supported", b="unknown")
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=ledger),
        decision("RELEASE", reason="A local repair passed."),
    ])

    assert monitor.review(packet(1)) == ""
    assert monitor.root_obligation_audit == ledger
    assert monitor.open_episode is None
    assert monitor.review(packet(2)) == ""
    assert monitor.root_obligation_audit == ledger


def test_first_control_decision_requires_persistent_root_ledger(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=[]),
        decision("SILENT", root_obligation_audit=root_audit(b="unknown")),
    ])
    monitor.root_obligation_audit = []

    assert monitor.review(packet(1)) == ""
    assert monitor.root_obligation_audit[1]["status"] == "unknown"
    assert "No persistent root obligation ledger exists yet" in session.prompts[1]


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
    # INSPECT is an intermediate investigation response, not an atomic final
    # decision, so its incidental ledger payload cannot mutate authority.
    assert monitor.root_obligation_audit == root_audit()
    assert monitor.decisions[-1]["control_valid"] is False
    assert "inspection budget" in monitor.decisions[-1]["reason"]


def test_checkpoint_restart_reconnects_root_episode_and_raw_archives(monkeypatch, tmp_path):
    first_session = FakeSession([
        decision(
            "HOLD",
            message="Repair B and show its behavior.",
            discrepancy="B conflicts with the root task.",
            exit_condition="A direct B observation passes.",
            root_obligation_audit=root_audit(b="contested"),
        )
    ])
    monkeypatch.setattr(m0, "resolve_session", lambda _: first_session)
    first = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor",
    )
    assert first.review(packet(1)) == "Repair B and show its behavior."

    second_session = FakeSession([decision("SILENT")])
    monkeypatch.setattr(m0, "resolve_session", lambda _: second_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor",
    )

    assert resumed.root_obligation_audit[1]["status"] == "contested"
    assert resumed.open_episode["original_discrepancy"] == "B conflicts with the root task."
    assert len(resumed.trajectory) == 1
    assert len(resumed.decisions) == 1
    assert resumed.review(packet(2)) == ""
    assert len(resumed.trajectory) == 2
    assert len(resumed.decisions) == 2
    assert "durable_monitor_checkpoint" in second_session.prompts[0]


def test_legacy_checkpoint_root_ledger_is_quarantined_for_rebootstrap(monkeypatch, tmp_path):
    task = "Implement A and B; demonstrate both."
    artifact_dir = tmp_path / "legacy-root-ledger"
    artifact_dir.mkdir()
    import hashlib
    (artifact_dir / "monitor_checkpoint.json").write_text(json.dumps({
        "schema_version": "m0-monitor-checkpoint/1",
        "public_task_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "root_obligation_audit": [
            {"obligation_id": "duplicate-custom", "obligation": "Implement A", "status": "supported",
             "public_evidence": ["A evidence"]},
            {"obligation_id": "duplicate-custom", "obligation": "Demonstrate B", "status": "unknown",
             "public_evidence": []},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))

    restored = m0.M0DeliberativeMonitor(
        public_task=task, workspace=tmp_path, config_name="fake",
        artifact_dir=artifact_dir,
    )

    assert restored.root_obligation_audit == []
    assert restored.legacy_root_ledger_requires_rebootstrap is True


def test_legacy_task_cognition_does_not_enter_clean_rebootstrap(monkeypatch, tmp_path):
    task = "Implement A and B; demonstrate both."
    artifact_dir = tmp_path / "legacy-cognition"
    artifact_dir.mkdir()
    import hashlib
    legacy_marker = "POLLUTED_LEGACY_COGNITION"
    (artifact_dir / "monitor_checkpoint.json").write_text(json.dumps({
        "schema_version": "m0-monitor-checkpoint/2",
        "public_task_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "root_obligation_audit": root_audit(),
        "m35_bootstrap_initialized": True,
        "m35_cognitive_checkpoint": {"continuation_note": legacy_marker},
        "m35_monitor_history": [
            {"role": "user", "content": [{"type": "text", "text": "old policy"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "old ack"}]},
            {"role": "user", "content": [{"type": "text", "text": legacy_marker}]},
        ],
    }), encoding="utf-8")
    response = {
        "root_obligation_audit": [
            {"obligation": "Implement A", "status": "unknown", "public_evidence": []},
            {"obligation": "Implement B", "status": "unknown", "public_evidence": []},
        ],
        "cognitive_checkpoint": {
            "continuation_note": "Preserve both clauses until public evidence exists.",
            "source_anchors": ["original public task"],
        },
        "observation_plan": {"review_after_turns": 10},
    }
    session = FakeSession([response])
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task=task, workspace=tmp_path, config_name="fake",
        artifact_dir=artifact_dir, m1_workspace_enabled=True,
        active_reconstruction_enabled=True, m2_semantic_impact_enabled=True,
        m3_human_loop_enabled=True, m3_decision_value_enabled=True,
        adaptive_review_planning_enabled=True, m35_continuity_enabled=True,
    )

    monitor.bootstrap_task_state()

    assert legacy_marker not in session.prompts[0]
    assert monitor.root_obligation_audit[0]["obligation_id"] == "obligation:0000"


def test_m35_release_bookmark_is_bounded_and_navigation_only(monkeypatch, tmp_path):
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Reconcile B with its public contract.",
            discrepancy="B contradicts the public contract.",
            exit_condition="A direct public B probe agrees with the contract.",
            decision_value={"live_decision": "Whether B is safe to release."},
            observation_plan={"review_after_turns": 1, "focus": "B repair uptake"},
        ),
        decision(
            "RELEASE", reason="The direct B probe now agrees.",
            public_anchors=["turn 2 direct B probe"],
            decision_value={"live_decision": "No local repair decision remains."},
            observation_plan={"review_after_turns": 12, "focus": "remaining root work"},
        ),
        decision("SILENT"),
    ])

    assert monitor.review(packet(1))
    protected_start = monitor.open_episode_history_start
    assert protected_start == 2
    assert monitor.review(packet(2)) == ""
    bookmark = monitor.last_closed_repair
    assert monitor.open_episode is None
    assert bookmark["original_discrepancy"] == "B contradicts the public contract."
    assert bookmark["release_evidence"] == ["turn 2 direct B probe"]
    assert "Navigation only" in bookmark["use"]
    assert bookmark["history_reference"]["from_message"] == protected_start
    assert bookmark["history_reference"]["through_message"] >= protected_start
    assert monitor.open_episode_history_start is None

    assert monitor.review(packet(3)) == ""
    prompt = session.prompts[-1]
    assert '"m3_decision_value"' in prompt
    assert '"m32_observation_plan"' in prompt
    assert '"m35_last_closed_repair"' in prompt
    assert monitor.decisions[-1]["intervention_message"] == ""


def test_m35_restart_restores_cumulative_monitor_continuity(monkeypatch, tmp_path):
    first, _ = build_m35_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Check the public B conflict.",
            discrepancy="B conflicts with the task.", exit_condition="B is re-observed.",
            decision_value={"live_decision": "Whether to continue B repair."},
            observation_plan={"review_after_turns": 2, "focus": "B evidence"},
        ),
        decision(
            "RELEASE", reason="B was re-observed from public evidence.",
            public_anchors=["turn 2 B evidence"],
            decision_value={"live_decision": "Return to root progress."},
            observation_plan={"review_after_turns": 9, "focus": "root completion"},
        ),
    ])
    first.review(packet(1))
    first.review(packet(2))

    resumed_session = FakeSession([decision("SILENT")])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True,
    )

    assert resumed.root_obligation_audit == root_audit()
    assert resumed.attention_mode == "patrol"
    assert resumed.open_episode is None
    assert resumed.decision_value["live_decision"] == "Return to root progress."
    assert resumed.observation_plan["review_after_turns"] == 9
    assert resumed.last_closed_repair["closed_turn"] == 2
    assert resumed.review(packet(3)) == ""
    assert "turn 2 B evidence" in resumed_session.prompts[0]


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
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True,
    )

    assert resumed.open_episode is not None
    assert resumed.open_episode_history_start == protected_start
    resumed.review(packet(2))
    assert resumed.open_episode_history_start == protected_start
    assert "Keep the B repair aligned" in json.dumps(
        resumed_session.message_batches[0], ensure_ascii=False
    )


def test_m35_cognitive_checkpoint_turns_next_wake_into_incremental_continuation(
        monkeypatch, tmp_path):
    first_note = (
        "I am following whether the Agent's B repair preserves the public contract. "
        "The direct probe is still missing; next inspect the Agent's stated probe intent "
        "and its result, then release only if they discriminate B's required behavior."
    )
    second_note = (
        "The Agent has proposed a direct B probe. I am waiting for its public result; "
        "do not reopen unrelated root work unless that result changes the repair scope."
    )
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [
        decision(
            "HOLD", message="Run the direct public B probe before changing B again.",
            discrepancy="B was changed from an unvalidated causal diagnosis.",
            exit_condition="The direct B probe discriminates the competing diagnoses.",
            cognitive_checkpoint={
                "continuation_note": first_note,
                "source_anchors": ["turn 1 B diagnosis", "tests/test_b.py"],
            },
        ),
        decision(
            "SILENT", attention_mode="focused",
            cognitive_checkpoint={
                "continuation_note": second_note,
                "source_anchors": ["turn 2 proposed B probe"],
            },
        ),
    ])

    first_packet = packet(1)
    first_packet["archive_delta"] = {"last_sequence": 8}
    monitor.review(first_packet)
    assert monitor.cognitive_checkpoint["continuation_note"] == first_note
    assert monitor.cognitive_checkpoint["reviewed_through_archive_sequence"] == 8

    second_packet = packet(2)
    second_packet["archive_delta"] = {"last_sequence": 10}
    monitor.review(second_packet)
    prompt = session.prompts[1]
    assert '"continuation_mode": "checkpoint_plus_delta"' in prompt
    assert first_note in prompt
    assert '"last_root_obligation_audit"' not in prompt
    assert '"root_state_directory"' in prompt
    assert monitor.cognitive_checkpoint["continuation_note"] == second_note
    assert monitor.cognitive_checkpoint["reviewed_through_archive_sequence"] == 10


def test_m35_uses_one_persistent_monitor_thread_with_stable_observation_map(
        monkeypatch, tmp_path):
    first_note = "I am waiting for the public B probe result."
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [
        decision("SILENT", attention_mode="focused", cognitive_checkpoint={
            "continuation_note": first_note,
            "source_anchors": ["turn 1 B probe intent"],
        }),
        decision("SILENT", cognitive_checkpoint={
            "continuation_note": "The B probe result is now available.",
            "source_anchors": ["turn 2 B probe result"],
        }),
    ])

    h0 = monitor.history[0]["content"][0]["text"]
    assert "STABLE GENERICAGENT OBSERVATION MAP" in h0
    assert "read_public_trajectory accepts start_turn/end_turn/limit" in h0
    assert "list_changed_tests lists changed test paths" in h0
    # The adapter documents affordances; the monitor constitution and live
    # judgment decide how and when those affordances are used.
    assert "Choose tools from the investigation" not in h0
    assert "tests support only their demonstrated scope" not in h0
    monitor.review(packet(1))
    first_raw = monitor.history[-1]["content"][0]["text"]
    monitor.review(packet(2))

    second_messages = session.message_batches[1]
    assert len(second_messages) == 5
    assert second_messages[0] == session.message_batches[0][0]
    assert first_raw in [
        block["text"]
        for message in second_messages[:-1]
        for block in message["content"]
    ]
    assert first_note in first_raw


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
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True,
    )

    assert resumed.history[2:] == saved_tail
    assert resumed.history[:2] != []
    resumed.review(packet(2))
    restored_messages = resumed_session.message_batches[0]
    assert first_note in json.dumps(restored_messages, ensure_ascii=False)
    assert first_session.message_batches[0][0] == restored_messages[0]


def test_m35_completion_uses_wide_state_even_with_cognitive_checkpoint(
        monkeypatch, tmp_path):
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [
        decision(
            "SILENT",
            cognitive_checkpoint={
                "continuation_note": "I am in ordinary patrol after reviewing A.",
                "source_anchors": ["turn 1 A result"],
            },
        ),
        decision(
            "SILENT", root_obligation_audit=root_audit(),
            cognitive_checkpoint={
                "continuation_note": "Root completion was audited against A and B.",
                "source_anchors": ["root completion proposal"],
            },
        ),
    ])
    monitor.review(packet(1))
    monitor.review_completion(SimpleNamespace(response_preview="A and B are done"), 2)

    completion_prompt = session.prompts[1]
    assert '"continuation_mode": "wide_reconstruction"' in completion_prompt
    assert '"last_root_obligation_audit"' in completion_prompt


def test_m35_restart_restores_authored_cognitive_checkpoint(monkeypatch, tmp_path):
    note = "I am waiting for the Agent's next public B result before revising my judgment."
    first, _ = build_m35_monitor(monkeypatch, tmp_path, [
        decision(
            "SILENT", attention_mode="focused",
            cognitive_checkpoint={
                "continuation_note": note,
                "source_anchors": ["turn 1 B intent"],
            },
        )
    ])
    first.review(packet(1))

    resumed_session = FakeSession([decision(
        "SILENT", cognitive_checkpoint={
            "continuation_note": "The B result arrived; resume ordinary patrol.",
            "source_anchors": ["turn 2 B result"],
        },
    )])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-m35",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True,
    )

    assert resumed.cognitive_checkpoint["continuation_note"] == note
    resumed.review(packet(2))
    assert note in resumed_session.prompts[0]


def test_h4_requires_persistent_history(monkeypatch, tmp_path):
    monkeypatch.setattr(m0, "resolve_session", lambda _: FakeSession([]))
    with pytest.raises(ValueError, match="minimal front stage requires"):
        m0.M0DeliberativeMonitor(
            public_task="Implement A.", workspace=tmp_path, config_name="fake",
            m35_minimal_frontstage_enabled=True,
        )


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
    assert "m35_cognitive_checkpoint" not in prompt
    assert "semantic_workspace_index" not in prompt
    h0 = session.message_batches[0][0]["content"][0]["text"]
    assert "STABLE MONITOR CALL PROTOCOL" in h0
    assert "no separate cognitive checkpoint is required" in h0
    assert "M2-C semantic impact proposals are enabled" in h0
    assert "observation_plan is an optional durable update" in h0
    assert "the world\ncontinued while you were quiet" in h0
    assert "choose the source, scope, and depth yourself" in h0
    assert "fixed inspection ritual or checklist" in h0
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
    assert "VISIBLE_1_" not in json.dumps(checkpoint["m35_monitor_history"], ensure_ascii=False)

    resumed_session = FakeSession([decision("SILENT")])
    monkeypatch.setattr(m0, "resolve_session", lambda _: resumed_session)
    resumed = m0.M0DeliberativeMonitor(
        public_task="Implement A and B; demonstrate both.", workspace=tmp_path,
        config_name="fake", artifact_dir=tmp_path / "monitor-h4",
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True, m35_history_compaction_enabled=True,
        m35_minimal_frontstage_enabled=True,
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
        m1_workspace_enabled=True, active_reconstruction_enabled=True,
        m2_semantic_impact_enabled=True, m3_human_loop_enabled=True,
        m3_decision_value_enabled=True, adaptive_review_planning_enabled=True,
        m35_continuity_enabled=True, m35_history_compaction_enabled=True,
        m35_minimal_frontstage_enabled=True,
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


def test_h4_off_retains_previous_active_reconstruction_prompt(monkeypatch, tmp_path):
    monitor, session = build_m35_monitor(monkeypatch, tmp_path, [decision("SILENT")])
    monitor.review(packet(3))
    assert "CURRENT PUBLIC BOUNDARY" in session.prompts[0]
    assert '"root_state_directory"' in session.prompts[0]


def test_v1_checkpoint_attention_is_migrated_without_driving_v2_decisions(
        monkeypatch, tmp_path):
    task = "Implement A and B; demonstrate both."
    artifact_dir = tmp_path / "monitor"
    artifact_dir.mkdir()
    import hashlib
    (artifact_dir / "monitor_checkpoint.json").write_text(json.dumps({
        "schema_version": "m0-monitor-checkpoint/1",
        "public_task_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "attention_mode": "DELIBERATE",
        "open_repair_episode": {
            "opened_turn": 4,
            "original_discrepancy": "legacy public conflict",
            "original_exit_condition": "observable uptake",
        },
        "root_obligation_audit": root_audit(),
    }), encoding="utf-8")
    session = FakeSession([
        v2_decision(
            attention_mode="focused", notes="continue observing",
            root_obligation_audit=root_audit(),
        )
    ])
    monkeypatch.setattr(m0, "resolve_session", lambda _: session)
    monitor = m0.M0DeliberativeMonitor(
        public_task=task, workspace=tmp_path, config_name="fake",
        artifact_dir=artifact_dir,
    )

    # A pre-identity repair episode is not trusted as live control state.
    assert monitor.attention_mode == "patrol"
    assert monitor.review(packet(5)) == ""
    assert monitor.decisions[-1]["schema_version"] == "m0-monitor-decision/2"
    assert "action" not in monitor.decisions[-1]


def test_root_completion_prompt_restores_original_scope(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=root_audit())
    ])

    monitor.review_completion(SimpleNamespace(response_preview="local helper is done"), 28)

    prompt = session.prompts[0]
    assert "proposal is for the ROOT TASK" in prompt
    assert "last_root_obligation_audit" in prompt
    assert "Implement A and B; demonstrate both." in monitor.history[0]["content"][0]["text"]


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


def test_sparse_natural_root_update_binds_without_model_ids(monkeypatch, tmp_path):
    update = v2_decision(
        root_obligation_updates=[{
            "obligation_ref": "Implement B",
            "status": "contested",
            "public_evidence": ["turn 9: B test contradicts the contract"],
        }],
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [update])

    monitor.review(packet(9))

    assert monitor.root_obligation_audit[0]["status"] == "supported"
    assert monitor.root_obligation_audit[1]["obligation_id"] == "obligation:0001"
    assert monitor.root_obligation_audit[1]["status"] == "contested"


def test_sparse_root_update_ignores_stale_model_id(monkeypatch, tmp_path):
    update = v2_decision(root_obligation_updates=[{
        "obligation_id": "obligation:0000",
        "obligation_ref": "Implement B",
        "status": "contested",
        "public_evidence": ["turn 10: B conflicts with the contract"],
    }])
    monitor, _ = build_monitor(monkeypatch, tmp_path, [update])

    monitor.review(packet(10))

    assert monitor.root_obligation_audit[0]["status"] == "supported"
    assert monitor.root_obligation_audit[1]["status"] == "contested"


def test_sparse_root_update_accumulates_public_evidence(monkeypatch, tmp_path):
    update = v2_decision(root_obligation_updates=[{
        "obligation_ref": "Implement B",
        "status": "contested",
        "public_evidence": ["turn 10: later contradictory observation"],
    }])
    monitor, _ = build_monitor(monkeypatch, tmp_path, [update])

    monitor.review(packet(10))

    assert monitor.root_obligation_audit[1]["public_evidence"] == [
        "B implementation and discriminating test",
        "turn 10: later contradictory observation",
    ]


def test_mixed_ambiguous_sparse_patch_is_atomic_but_intervention_survives(
        monkeypatch, tmp_path):
    intervention = "Recheck B against the original public contract."
    value = v2_decision(
        intervention=intervention, attention_mode="focused",
        discrepancy="B has contradictory public evidence.",
        exit_condition="A contract-faithful B probe resolves the conflict.",
        root_obligation_updates=[{
            "obligation_ref": "Implement B", "status": "contested",
            "public_evidence": ["turn 12 B conflict"],
        }, {
            "obligation_ref": "Implement", "status": "unknown",
            "public_evidence": [],
        }],
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [value])
    original = json.loads(json.dumps(monitor.root_obligation_audit))

    assert intervention in monitor.review(packet(12))
    assert monitor.root_obligation_audit == original
    assert monitor.decisions[-1]["root_obligation_binding_ambiguities"]


def test_sparse_and_full_root_representations_cannot_bypass_atomic_rejection(
        monkeypatch, tmp_path):
    intervention = "Recheck B before relying on the current completion evidence."
    value = v2_decision(
        intervention=intervention, attention_mode="focused",
        discrepancy="B has contradictory public evidence.",
        exit_condition="A direct B probe resolves the conflict.",
        root_obligation_updates=[{
            "obligation_ref": "Implement B", "status": "contested",
            "public_evidence": ["turn 13 B conflict"],
        }],
        root_obligation_audit=root_audit(a="unknown", b="unknown"),
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [value])
    original = json.loads(json.dumps(monitor.root_obligation_audit))

    assert intervention in monitor.review(packet(13))

    assert monitor.root_obligation_audit == original
    assert "cannot combine" in " ".join(
        monitor.decisions[-1]["root_obligation_binding_ambiguities"]
    )


def test_ambiguous_natural_update_preserves_ledger_but_not_intervention(
        monkeypatch, tmp_path):
    intervention = "Recheck the public B conflict before closing the task."
    value = v2_decision(
        intervention=intervention, attention_mode="focused",
        discrepancy="B conflicts with the original requirement.",
        exit_condition="B has direct contract-faithful evidence.",
        root_obligation_updates=[{
            "obligation_ref": "Implement",
            "status": "contested",
            "public_evidence": ["turn 11 conflict"],
        }],
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [value])
    original = json.loads(json.dumps(monitor.root_obligation_audit))

    assert intervention in monitor.review(packet(11))
    assert monitor.root_obligation_audit == original
    assert monitor.decisions[-1]["root_obligation_binding_ambiguities"]


def test_completion_accepts_explicit_empty_semantic_patch_not_full_snapshot(
        monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        v2_decision(
            completion="allow_complete", root_obligation_updates=[],
            unresolved_unknown="No unresolved root uncertainty remains.",
        )
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 15)

    assert result.decision == "ALLOW_COMPLETE"
    assert [row["obligation_id"] for row in monitor.root_obligation_audit] == [
        "obligation:0000", "obligation:0001",
    ]


def test_ambiguous_semantic_patch_cannot_release_root_completion(
        monkeypatch, tmp_path):
    ambiguous = v2_decision(
        completion="allow_complete",
        root_obligation_updates=[{
            "obligation_ref": "Implement",
            "status": "supported",
            "public_evidence": ["generic claim"],
        }],
    )
    repair = v2_decision(
        intervention="Keep B open until its direct evidence exists.",
        attention_mode="focused", completion="continue_task",
        discrepancy="B remains unsupported.",
        exit_condition="A direct B probe passes.",
        root_obligation_updates=[{
            "obligation_ref": "Implement B",
            "status": "unknown", "public_evidence": [],
        }],
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [ambiguous, repair])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 16)

    assert result.decision == "CONTINUE"
    assert monitor.root_obligation_audit[1]["status"] == "unknown"


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
