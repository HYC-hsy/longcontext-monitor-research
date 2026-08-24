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
        self.max_tokens = 1024
        self.reasoning_effort = "xhigh"

    def raw_ask(self, messages):
        # M0 is one persistent conversation. Record the newest review or
        # protocol-correction turn, not the immutable policy at index zero.
        self.prompts.append(messages[-1]["content"][0]["text"])
        yield json.dumps(self.responses.pop(0))


def decision(action, **overrides):
    value = {
        "action": action,
        "epistemic_status": "confirmed_conflict" if action == "HOLD" else "watch",
        "intervention_mode": "repair" if action == "HOLD" else "none",
        "imminent_action_anchor": "",
        "reason": "public reason",
        "message": "",
        "public_anchors": ["task clause"],
        "discrepancy": "",
        "exit_condition": "",
        "authority_basis": "correctness_evidence" if action == "HOLD" else "none",
        "material_task_impact": "The public task can be completed incorrectly." if action == "HOLD" else "",
        "why_silence_is_insufficient": "The next action would close over the discrepancy." if action == "HOLD" else "",
        "evidence_availability": "obtainable_now" if action in {"HOLD", "ABSTAIN"} else "not_applicable",
        "next_safe_action": "Run the public discriminating probe." if action in {"HOLD", "ABSTAIN"} else "",
        "unresolved_unknown": "",
        "notes": "persistent notes",
    }
    value.update(overrides)
    return value


def root_audit(a="supported", b="supported"):
    return [
        {"obligation": "Implement A", "status": a,
         "public_evidence": ["A implementation and discriminating test"] if a == "supported" else []},
        {"obligation": "Implement B", "status": b,
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
    assert monitor.attention_mode == "DELIBERATE"
    assert "assert feature_a" in session.prompts[1]
    saved = json.loads((tmp_path / "monitor" / "decision_0001.json").read_text(encoding="utf-8"))
    assert saved["action"] == "HOLD"
    assert saved["inspections"][0]["result"]["ok"] is True


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
    assert monitor.attention_mode == "SHADOW"
    assert [row["action"] for row in monitor.decisions] == ["HOLD", "HOLD", "RELEASE"]


def test_silent_is_a_real_decision_and_does_not_open_episode(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [decision("SILENT", notes="public signal is faithful")])
    assert monitor.review(packet()) == ""
    assert monitor.open_episode is None
    assert monitor.decisions[0]["action"] == "SILENT"
    assert monitor.attention_mode == "SHADOW"
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
    assert '"action": "SILENT"' in session.prompts[2]


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
        decision("SILENT", notes="agent is investigating"),
        {"action": "INSPECT", "reason": "review uptake", "inspection": {
            "operation": "read_repair_episode", "limit": 10,
        }},
        decision("SILENT", notes="repair continues"),
    ])
    monitor.review(packet(1))
    monitor.review(packet(2))
    assert monitor.attention_mode == "DELIBERATE"
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
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("SILENT", root_obligation_audit=root_audit())
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 24)

    assert result.decision == "ALLOW_COMPLETE"
    assert result.reason_codes == ("M0_SILENT",)


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
    assert result.reason_codes == ("M0_RELEASE",)
    assert monitor.decisions[-1]["unresolved_unknown"].startswith("Runtime behavior")
    assert monitor.open_episode is None
    assert "RELEASE_WITH_UNKNOWN" in session.prompts[1]


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
    assert monitor.decisions[-1]["hold_repeat_count"] == 2
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
    assert monitor.decisions[-1]["action"] == "SILENT"
    assert "watch-level risk cannot HOLD" in session.prompts[1]


def test_uncertain_causality_silence_is_monitor_judgment_not_protocol_override(
        monkeypatch, tmp_path):
    probe = decision(
        "HOLD", message="Run a direct control before changing production.",
        epistemic_status="causal_uncertainty", intervention_mode="discriminating_probe",
        imminent_action_anchor="Agent says it will change production from the new failing probe.",
        discrepancy="The failure may come from the test fixture or production.",
        next_safe_action="Compare the same fixture against a direct control.",
    )
    monitor, _ = build_monitor(monkeypatch, tmp_path, [probe, decision("SILENT")])

    first = monitor.review(packet(42))
    second = monitor.review(packet(43))

    assert "direct control" in first
    assert second == ""
    assert [row["action"] for row in monitor.decisions] == ["HOLD", "SILENT"]
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
    assert monitor.decisions[-1]["action"] == "HOLD"
    assert "control_valid" not in monitor.decisions[-1]


def test_completion_protocol_failure_cannot_silently_finish_root_task(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("RELEASE"), decision("RELEASE"), decision("RELEASE")
    ])

    result = monitor.review_completion(SimpleNamespace(response_preview="done"), 29)

    assert result.decision == "CONTINUE"
    assert result.reason_codes == ("M0_ABSTAIN",)
    assert "monitor could not complete its internal root-task audit" in result.next_prompt
    assert monitor.decisions[-1]["control_valid"] is False


def test_local_release_does_not_replace_root_release_basis(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("HOLD", message="Repair local A.", discrepancy="A conflict",
                 exit_condition="A focused probe"),
        decision("RELEASE", reason="A focused probe passed"),
    ])
    original_basis = monitor.root_task_release_basis

    monitor.review(packet(1))
    monitor.review(packet(2))

    assert monitor.open_episode is None
    assert monitor.root_task_release_basis == original_basis
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
    assert result.reason_codes == ("M0_ABSTAIN",)
    assert "monitor could not complete" in result.next_prompt
    assert monitor.root_obligation_audit == ledger
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


def test_invalid_or_empty_hold_is_rejected(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [
        decision("HOLD"),
        decision("HOLD"),
        decision("HOLD"),
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
    assert monitor.decisions[0]["action"] == "SILENT"
    assert "workflow noncompliance alone" in session.prompts[1]


def test_invalid_action_is_corrected_without_ending_task(monkeypatch, tmp_path):
    monitor, session = build_monitor(monkeypatch, tmp_path, [
        {"reason": "forgot action", "notes": "x"},
        decision("SILENT", reason="corrected"),
    ])
    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["action"] == "SILENT"
    assert "Invalid or missing action" in session.prompts[1]


def test_nested_decision_object_is_accepted(monkeypatch, tmp_path):
    monitor, _ = build_monitor(monkeypatch, tmp_path, [{"decision": decision("SILENT")}])
    assert monitor.review(packet()) == ""
    assert monitor.decisions[0]["action"] == "SILENT"


def test_turn_callback_injects_monitor_text_before_next_llm(tmp_path):
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

    assert "[M0 MONITOR" in result
    assert "Recheck clause B." in result
    assert calls[0]["response_content"] == "I am done"
    assert calls[0]["boundary"] == "post_tool_pre_next_llm"


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
