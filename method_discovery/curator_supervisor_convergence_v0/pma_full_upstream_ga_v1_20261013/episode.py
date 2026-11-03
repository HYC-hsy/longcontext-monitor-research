"""Pilot-only event adapter around the unmodified upstream PMA object.

This module never starts Terminus2's actor loop.  Its actor backend is a
deliberately unusable BaseLLM; only the upstream memory LiteLLM may infer.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pma_evidence_review.private_faults import EpisodeFault, record_failure

from harbor.llms.base import BaseLLM, LLMResponse
from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2


class DisabledActorLLM(BaseLLM):
    calls = 0

    async def call(self, prompt: str, **kwargs: Any) -> LLMResponse:
        self.calls += 1
        raise RuntimeError("Terminus2 actor is disabled; GA owns the task")

    def get_model_context_limit(self) -> int:
        return 200_000  # Inert metadata; the actor is never queried.

    def get_model_output_limit(self) -> int | None:
        return None


def stable_initial_text(content: str | list[dict[str, Any]]) -> str:
    """Preserve GA's actual pre-reminder user envelope deterministically."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return json.dumps(content, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"))
    raise TypeError("unsupported initial GA user content")


def construct_upstream(logs_dir: Path, *, memory_api_base: str | None = None,
                       memory_api_key: str | None = None,
                       memory_profile: dict[str, Any] | None = None,
                       research_candidate: str = "U",
                       citation_review_gate: str | None = None, citation_review_strategy: str | None = None,
                       memory_maintenance_policy: str | None = None) -> MemoryEnabledTerminus2:
    from citation_gate_config import (validate_gate,validate_strategy,validate_maintenance,
                                      BANK_DISPLAY_POLICY,REQUIREMENT_REMINDER_POLICY)
    validate_maintenance(memory_maintenance_policy,research_candidate,citation_review_gate,citation_review_strategy)
    validate_gate(citation_review_gate,research_candidate)
    review_strategy=validate_strategy(citation_review_gate,citation_review_strategy)
    if research_candidate not in {"U", "V1", "D1", "S", "R", "S2", "R2", "pma_gap_memory_v0", "pma_gap_evidence_v1"}:
        raise ValueError("unknown research candidate")
    if memory_profile is not None:
        if (memory_profile.get("provider"), memory_profile.get("api_mode"),
                memory_profile.get("model"), memory_profile.get("thinking_type")) != (
                "anthropic", "messages", "claude-opus-4-8", "adaptive"):
            raise ValueError("PMA memory profile is not the frozen Opus 4.8 route")
        if not memory_profile.get("apibase") or not memory_profile.get("apikey"):
            raise ValueError("PMA memory profile lacks transport configuration")
    actor = DisabledActorLLM()
    agent = MemoryEnabledTerminus2(
        logs_dir=logs_dir, model_name="disabled-actor-not-ga-task-model",
        llm=actor, parser_name="xml", record_terminal_session=False,
        memory_model_name=("anthropic/claude-opus-4-8" if memory_profile is not None
                           else "openrouter/anthropic/claude-opus-4.6"),
        memory_api_base=(memory_profile["apibase"] if memory_profile is not None
                         else memory_api_base),
        memory_api_key=(memory_profile["apikey"] if memory_profile is not None
                        else memory_api_key),
        memory_temperature=(memory_profile["temperature"] if memory_profile is not None
                            else 0.3), memory_max_thinking_tokens=None,
        memory_keep_thinking=False, memory_use_structured_tools=True,
        trigger_interval=1, trigger_on_first_step=True,
        sliding_window_size=8, reset_status_on_episode=True,
        reset_knowledge_on_episode=False, reset_procedural_on_episode=False,
        injection_method="user_turn",
    )
    if agent._llm is not actor:
        raise RuntimeError("upstream actor backend was not disabled")
    if research_candidate in {"V1", "D1"}:
        from decision_reminder_agent import DecisionReminderAgent
        original = agent._memory_agent
        agent._memory_agent = DecisionReminderAgent(
            variant=research_candidate, llm=agent._memory_llm,
            memory=agent._memory,
            max_memory_in_prompt=original.max_memory_in_prompt,
            use_bm25_prefilter=original.use_bm25_prefilter,
            keep_thinking=original.keep_thinking,
            use_structured_tools=original.use_structured_tools)
        agent._research_candidate = research_candidate
    elif research_candidate in {"pma_gap_memory_v0", "pma_gap_evidence_v1"}:
        if research_candidate == "pma_gap_evidence_v1":
            from latest_evidence_gap_agent import LatestEvidenceGapMemoryAgent as GapMemoryAgent
            from latest_evidence_gap_store import LatestEvidenceGapMemory as GapMemory
        else:
            from gap_memory_agent import GapMemoryAgent
            from gap_store import GapMemory
        original = agent._memory_agent
        if memory_maintenance_policy in (BANK_DISPLAY_POLICY,REQUIREMENT_REMINDER_POLICY):
            from bank_display_agent import BankDisplayAgent
            bank = BankDisplayAgent.load_bank(agent._memory.to_dict())
        else:
            bank = GapMemory.from_dict(agent._memory.to_dict())
        agent._memory = bank
        agent._memory_agent = GapMemoryAgent(
            task="", llm=agent._memory_llm, memory=bank,
            max_memory_in_prompt=original.max_memory_in_prompt,
            use_bm25_prefilter=original.use_bm25_prefilter,
            keep_thinking=original.keep_thinking,
            use_structured_tools=original.use_structured_tools)
        if memory_maintenance_policy == REQUIREMENT_REMINDER_POLICY:
            # The P1 archive must be created only after the real original task arrives.
            agent._memory_maintenance_policy = REQUIREMENT_REMINDER_POLICY
            agent._requirement_source_root = Path(logs_dir)/'requirement_sources'
        elif memory_maintenance_policy is not None:
            if memory_maintenance_policy == BANK_DISPLAY_POLICY:
                policy_class = BankDisplayAgent
            else:
                from maintenance_no_review_agent import MaintenanceNoReviewAgent
                policy_class = MaintenanceNoReviewAgent
            agent._memory_agent = policy_class(
                task="", llm=agent._memory_llm, memory=bank,
                max_memory_in_prompt=original.max_memory_in_prompt,
                use_bm25_prefilter=original.use_bm25_prefilter,
                keep_thinking=original.keep_thinking,
                use_structured_tools=original.use_structured_tools)
            agent._memory_maintenance_policy=memory_maintenance_policy
        if citation_review_gate is not None:
            from citation_gate_agent import CitationGateMemoryAgent
            from verbatim_selection_agent import VerbatimSelectionCitationGateAgent
            candidate_gate_class = (VerbatimSelectionCitationGateAgent
                                    if review_strategy == 'claim-split-same-evidence-v4'
                                    else CitationGateMemoryAgent)
            agent._memory_agent = candidate_gate_class(
                task="", llm=agent._memory_llm, memory=bank,
                max_memory_in_prompt=original.max_memory_in_prompt,
                use_bm25_prefilter=original.use_bm25_prefilter,
                keep_thinking=original.keep_thinking,
                use_structured_tools=original.use_structured_tools,
                review_directory=Path(logs_dir)/"citation_review",
                repair_limit=int(citation_review_gate=='gate-one-repair'),review_strategy=review_strategy)
            agent._citation_review_gate=citation_review_gate
            agent._citation_review_strategy=review_strategy
        if agent._memory is not agent._memory_agent.memory or agent._memory is not agent._memory_agent.gaps:
            raise RuntimeError("gap bank identity mismatch")
        agent._research_candidate = research_candidate
    elif research_candidate != "U":
        # Preserve the original trigger, process, two provider calls, BM25 and
        # reminder consumption. Only the bank and prompt/tool adapters differ.
        from source_agent import SourceMemoryAgent
        from source_agent_v2 import SourceMemoryAgentV2
        from source_memory import SourceMemory
        from source_memory_v2 import SourceMemoryV2
        bank = SourceMemoryV2() if research_candidate in {"S2", "R2"} else SourceMemory()
        agent._memory = bank
        candidate_class = SourceMemoryAgentV2 if research_candidate in {"S2", "R2"} else SourceMemoryAgent
        agent._memory_agent = candidate_class(
            variant=research_candidate, llm=agent._memory_llm, memory=bank,
            keep_thinking=False, use_structured_tools=True)
        agent._research_candidate = research_candidate
    if memory_profile is not None:
        # Transport-only adaptation. The upstream memory prompts, bank, trigger,
        # two-phase process, and LiteLLM retry decorator remain unchanged.
        memory_llm = agent._memory_llm
        memory_llm._reasoning_effort = memory_profile["reasoning_effort"]
        original_call = memory_llm.call

        async def profiled_call(*, prompt, system, tools=None):
            return await original_call(
                prompt=prompt, system=system, tools=tools,
                max_tokens=memory_profile["max_tokens"],
                thinking={"type": "adaptive"},
                timeout=memory_profile["read_timeout"],
            )

        memory_llm.call = profiled_call
    return agent


class PMAEpisode:
    """One task, one original object, one serial asyncio loop, no actor run."""

    def __init__(self, agent: MemoryEnabledTerminus2, *, run_id: str,
                 task_id: str, archive: Path):
        self.agent = agent
        if hasattr(agent._memory_agent,'run_id'):
            agent._memory_agent.run_id=run_id
        self.run_id = run_id
        self.task_id = task_id
        self.archive = archive
        self.archive.mkdir(parents=True, exist_ok=False)
        self.started = False
        self.ended = False
        self.finalization_attempted = False
        self.last_attempt = 0
        self.last_completed_attempt = 0
        self.last_sequence = 0
        self._responses: dict[str, tuple[str, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()
        self._failure = None
        self._active_event_id = None
        self._requirement_entries = []

    async def _run_requirement_reminder(self, *, step_count: int) -> None:
        """The opt-in composed candidate; do not use upstream's silent error handler."""
        from p1_source_archive import encode
        pipeline = self.agent._requirement_pipeline
        p1, p2 = pipeline.p1, pipeline.p2
        before = self.agent._memory.to_dict()
        self.agent._memory_trigger_count += 1
        prompts = {}
        def p1_before(request):
            prompts['p1'] = request['prompt']
            p1.transport_phase = ('requirement_initialization' if
                                  request.get('kind') == 'requirement_initialization' else 'maintenance')
        def p2_before(request):
            prompts['p2'] = request['prompt']
            p1.transport_phase = 'selection'
        p1.before_request, p2.before_request = p1_before, p2_before
        entries = deepcopy(self._requirement_entries[-8:])
        report = await pipeline.run(entries, observation=self.agent._get_memory_agent_context(), step_count=step_count,
                                    cycle_id=f'{self.run_id}_step_{step_count}')
        report.update(mode='requirement_reminder_task_adapter',task_enabled=True)
        # Initialization validation has not executed maintenance or changed the bank.
        # Close this failed attempt explicitly so a later trigger can retry extraction.
        phase1 = report.get('p1') or {}
        if (report['status']=='p1_incomplete' and phase1.get('status')=='initialization_failed'
                and phase1.get('failure_kind') in {'model_output','transport'} and not phase1.get('operations')
                and p1.requirement_state.data['catalog'] is None and self.agent._memory.to_dict()==before):
            p1.requirement_state.phase(phase1['cycle_id'],'done',result=phase1)
            report.update(error_policy='continue_without_reminder',initialization_aborted_without_maintenance=True)
        from memory_agent.memory.memory_agent import MemoryAgentResult, MemoryOperation
        operations = [MemoryOperation(**{k:v for k,v in op.items() if k in
            {'action','memory_id','content','success','error'}}) for op in phase1.get('operations',[])]
        self.agent._memory_operation_count += len(operations)
        last_text = lambda phase: next((t.get('assistant_text') for t in reversed(
            (phase or {}).get('turns') or (phase or {}).get('initialization_attempts',[]))),None)
        recorded = MemoryAgentResult(operations=operations,should_inject=bool(report['should_inject']),
            context_for_action=report['context_for_action'],raw_response_phase1=last_text(phase1),
            raw_response_phase2=last_text(report.get('p2')),
            user_prompt_phase1=prompts.get('p1'),user_prompt_phase2=prompts.get('p2'))
        self.agent._record_memory_step(trigger_step=self.agent._memory_step_in_episode,
            step_count=step_count,observation=self.agent._get_memory_agent_context(),result=recorded)
        entry = self.agent._memory_trajectory_steps[-1]
        entry['requirement_cycle_status'] = report['status']
        entry['memory_snapshot']['gap_count'] = len(self.agent._memory.entries)
        if report.get('p1_warning'):
            entry['memory_warning'] = {'phase':'p1','status':phase1['status'],
                'failure_kind':phase1.get('failure_kind','model_tool'),'error_type':phase1.get('error_type')}
        if report['status'] not in ('intervention','no_intervention'):
            self.agent._memory_trajectory_steps[-1]['memory_error'] = {
                'status':report['status'],'failure_kind':report.get('failure_kind','engineering'),
                'error_policy':report.get('error_policy','fail_stop')}
        row = {'step':step_count,'entries':entries,'bank_before':before,
               'bank_after':self.agent._memory.to_dict(),'report':report}
        with (self.archive/'requirement_cycles.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(encode(row)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
        self._last_requirement_cycle_status = report['status']
        if report['status'] not in ('intervention','no_intervention') or report.get('p1_warning'):
            self.agent._requirement_memory_error_count = getattr(self.agent,'_requirement_memory_error_count',0)+1
        if report['status'] not in ('intervention','no_intervention'):
            if report.get('error_policy')=='continue_without_reminder':
                return
            raise RuntimeError('requirement reminder cycle failed: '+report['status'])
        if report['should_inject']:
            self.agent._pending_injection = report['context_for_action']
            self.agent._injection_used = False
            self.agent._injection_count += 1
        else:
            self.agent._noop_count += 1

    def _record(self, event: dict[str, Any], result: dict[str, Any]) -> None:
        line = json.dumps({"event": event, "result": result},
                          ensure_ascii=False, sort_keys=True)
        with (self.archive / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    @asynccontextmanager
    async def _event_boundary(self):
        async with self._lock:
            if self._failure is not None:
                # Same-worker fail-stop: never replay a partially executed event.
                raise EpisodeFault(self._failure)
            try:
                yield
            except Exception as error:
                failure = record_failure(self.archive, error, event_id=self._active_event_id)
                if self._active_event_id is not None:
                    self._failure = failure
                raise EpisodeFault(failure) from error
            finally:
                self._active_event_id = None

    async def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        async with self._event_boundary():
            if not isinstance(event, dict):
                raise ValueError("event must be an object")
            if (event.get("run_id"), event.get("task_id")) != (self.run_id, self.task_id):
                raise ValueError("event identity mismatch")
            event_id = event.get("event_id")
            sequence = event.get("sequence")
            if not isinstance(event_id, str) or not event_id or type(sequence) is not int:
                raise ValueError("event ID and integer sequence required")
            digest = hashlib.sha256(json.dumps(event, sort_keys=True,
                                               ensure_ascii=False).encode()).hexdigest()
            if event_id in self._responses:
                old_digest, old_result = self._responses[event_id]
                if old_digest != digest:
                    raise ValueError("event ID reused with different content")
                return old_result
            if sequence != self.last_sequence + 1:
                raise ValueError("event sequence gap or replay with unknown receipt")
            self._active_event_id = event_id
            accepted_path = self.archive / "accepted.jsonl"
            with accepted_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event_id": event_id, "sequence": sequence,
                                         "sha256": digest}, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            kind = event.get("kind")
            if kind == "task_start":
                result = await self._task_start(event)
            elif kind == "before_actor_call":
                result = self._before_actor_call(event)
            elif kind == "actor_step":
                result = await self._actor_step(event)
            elif kind == "task_end":
                result = self._task_end(event)
            else:
                raise ValueError("unknown PMA event kind")
            candidate_agent = self.agent._memory_agent
            report = getattr(candidate_agent, 'last_citation_gate_report', {})
            transport = getattr(candidate_agent, 'review_transport', None)
            if (report.get('diagnostic_write_error') or report.get('finalization_error')
                    or getattr(transport, 'audit_failure', None)):
                failure = report.get('diagnostic_failure') or getattr(transport, 'audit_failure', None) or {}
                raise RuntimeError('PMA audit persistence failed; prior_failure_id=' +
                                   failure.get('failure_id', 'unavailable'))
            self._record(event, result)
            if (getattr(self.agent, '_research_candidate', None) in {'pma_gap_memory_v0', 'pma_gap_evidence_v1'}
                    and getattr(self.agent,'_memory_maintenance_policy',None) != 'pma-requirement-reminder-v1'
                    and result.get('triggered')):
                with (self.archive / 'gap_cycle.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({
                        'run_id': self.run_id, 'task_id': self.task_id,
                        'event_id': event_id, 'sequence': sequence,
                        'step': 1 if kind == 'task_start' else result.get('step_count'),
                        'report': deepcopy(candidate_agent.last_gap_report),
                        **({'memory_maintenance_policy': candidate_agent.maintenance_policy}
                           if hasattr(candidate_agent, 'maintenance_policy') else {}),
                        'formal_gaps': [entry.to_dict() for entry in self.agent._memory.entries],
                        **({'alignment_policy': candidate_agent.expected_alignment_policy}
                           if hasattr(candidate_agent, 'expected_alignment_policy') else {}),
                        **({'citation_gate_report': deepcopy(candidate_agent.last_citation_gate_report)}
                           if hasattr(candidate_agent, 'last_citation_gate_report') else {}),
                        **({'evidence_report': deepcopy(candidate_agent.last_evidence_report)}
                           if hasattr(candidate_agent, 'last_evidence_report') else {}),
                    }, ensure_ascii=False, sort_keys=True) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
            if (hasattr(candidate_agent, "last_delivery_status")
                    and hasattr(candidate_agent, "variant")):
                with (self.archive / "candidate_audit.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({
                        "event_id": event_id, "kind": kind,
                        "candidate": candidate_agent.variant,
                        "phase2_status": candidate_agent.last_delivery_status,
                        "reminder_memory_refs": candidate_agent.last_reminder_refs,
                        "reminder_source_refs": [
                            self.agent._memory.metadata[ref["id"]]["source_refs"]
                            for ref in candidate_agent.last_reminder_refs
                            if ref["id"] in self.agent._memory.metadata],
                        "coordination": candidate_agent.coordination,
                        "transaction": (getattr(candidate_agent, "last_transaction", None)
                                        if result.get("triggered") else None),
                        "collateral_aborts": getattr(candidate_agent, "collateral_aborts", None),
                    }, ensure_ascii=False, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            if kind == "task_end" and result.get("status") == "saved":
                self.ended = True
            self.last_sequence = sequence
            self._responses[event_id] = (digest, result)
            return result

    async def _task_start(self, event: dict[str, Any]) -> dict[str, Any]:
        if self.started or self.ended:
            raise ValueError("task_start is only valid once")
        raw = event.get("initial_user_content")
        text = stable_initial_text(raw)
        if getattr(self.agent,'_memory_maintenance_policy',None) == 'pma-requirement-reminder-v1':
            from p1_requirement_agent import RequirementP1Agent
            from p2_requirement_reminder import RequirementReminderPipeline
            p1 = RequirementP1Agent(task=text,task_id=self.task_id,memory=self.agent._memory,
                llm=self.agent._memory_llm,source_root=self.agent._requirement_source_root)
            self.agent._memory_agent = p1
            self.agent._requirement_pipeline = RequirementReminderPipeline(p1)
        self.agent._memory_step_in_episode = 0
        self.agent._trigger.reset()
        self.agent._accumulated_observations.clear()
        self.agent._pending_injection = None
        self.agent._injection_used = False
        self.agent._task_description = text
        if getattr(self.agent, "_research_candidate", None) in {"pma_gap_memory_v0", "pma_gap_evidence_v1"}:
            self.agent._memory_agent.task = text
        if hasattr(self.agent._memory, "register_leaf"):
            self.agent._memory.register_leaf(event["event_id"], "task_instruction",
                text, event["sequence"], "initial_user_content", event["source_record_sha256"])
        elif hasattr(self.agent._memory, "register_source"):
            self.agent._memory.register_source(event["event_id"], "task_instruction",
                                               text, event["sequence"])
        if self.agent._reset_status_on_episode:
            self.agent._memory.update_status("")
        for reset, entries in (
                (self.agent._reset_knowledge_on_episode, self.agent._memory.knowledge),
                (self.agent._reset_procedural_on_episode, self.agent._memory.procedural)):
            if reset:
                if getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1":
                    for entry in list(entries):
                        self.agent._memory.delete_bound(entry.id, cycle_id="episode_reset")
                else:
                    entries.clear()
        self.agent._accumulate_step(step=1, observation=text)
        if getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1":
            from evidence_gap_context import event_identity
            self.agent._evidence_task_identity = event_identity(event)
        triggered, reason = self.agent._trigger.should_trigger(step_count=1)
        self.started = True
        if triggered:
            if getattr(self.agent,'_memory_maintenance_policy',None) == 'pma-requirement-reminder-v1':
                await self._run_requirement_reminder(step_count=1)
            elif getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1":
                from evidence_gap_context import prepare_context
                prepare_context(self.agent)
            elif getattr(self.agent, '_memory_maintenance_policy', None) == 'pma-bank-display-v1':
                self.agent._memory_agent.prepare_selection_context(
                    self.agent._get_memory_agent_context(),
                    self.agent._accumulated_observations[1:][-self.agent._sliding_window_size:])
            if getattr(self.agent,'_memory_maintenance_policy',None) != 'pma-requirement-reminder-v1':
                await self.agent._trigger_memory_agent(step_count=1)
        return {"status": "started", "triggered": triggered, "trigger_reason": reason,
                **({'memory_cycle_status':self._last_requirement_cycle_status} if hasattr(self,'_last_requirement_cycle_status') else {}),
                "initial_envelope_sha256": hashlib.sha256(
                    json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}

    def _before_actor_call(self, event: dict[str, Any]) -> dict[str, Any]:
        attempt = event.get("actor_attempt")
        if (not self.started or self.ended or type(attempt) is not int
                or attempt != self.last_attempt + 1
                or self.last_attempt != self.last_completed_attempt):
            raise ValueError("non-monotonic actor attempt")
        self.agent._memory_step_in_episode = attempt
        self.last_attempt = attempt
        candidate_agent = self.agent._memory_agent
        if getattr(self.agent,'_memory_maintenance_policy',None) == 'pma-requirement-reminder-v1' and self.agent._pending_injection:
            if not self.agent._requirement_pipeline.p2.pending_refs_valid():
                raise RuntimeError('requirement reminder invalid before Task delivery')
        if (getattr(self.agent,'_memory_maintenance_policy',None) != 'pma-requirement-reminder-v1'
                and hasattr(candidate_agent, "pending_refs_valid") and self.agent._pending_injection):
            if not candidate_agent.pending_refs_valid():
                self.agent._pending_injection = None
                candidate_agent.last_delivery_status = "invalid_reference_no_delivery"
        reminder = self.agent._get_memory_system_prompt()
        return {"status": "reminder" if reminder else "silent", "reminder": reminder,
                "actor_attempt": attempt, "delivery": "returned_not_confirmed_in_ga_request"}

    async def _actor_step(self, event: dict[str, Any]) -> dict[str, Any]:
        attempt = event.get("actor_attempt")
        if (not self.started or self.ended or attempt != self.last_attempt
                or attempt <= self.last_completed_attempt):
            raise ValueError("actor step does not match active attempt")
        status = event.get("step_status")
        if status in {"parse_error", "provider_cancelled", "completed"}:
            self.last_completed_attempt = attempt
            return {"status": "skipped", "reason": status, "actor_attempt": attempt}
        if status != "normal":
            raise ValueError("unknown actor step status")
        commands = event.get("commands", [])
        if not isinstance(commands, list) or not all(isinstance(c, str) for c in commands):
            raise ValueError("commands must be a list of original tool descriptions")
        observation = event.get("observation")
        if not isinstance(observation, str):
            raise ValueError("complete public observation required")
        # GA has no Terminus2 plan/analysis envelope.  Its complete public
        # response is the upstream analysis input; hidden thinking is never read.
        analysis = event.get("analysis")
        if analysis is None:
            analysis = event.get("response")
        if (hasattr(self.agent._memory, "register_source") or
                getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1"):
            # Candidate provenance accepts only GA's explicitly public body;
            # an auxiliary analysis field cannot be treated as visible text.
            analysis = event.get("response")
        if not isinstance(analysis, str):
            raise ValueError("complete public actor response required")
        plan = (None if getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1"
                else event.get("plan"))
        if plan is not None and not isinstance(plan, str):
            raise ValueError("plan must be text or absent")
        step = attempt + 1
        if hasattr(self.agent._memory, "register_source"):
            bank = self.agent._memory
            if hasattr(bank, "register_leaf"):
                raw_sha = event["source_record_sha256"]
                bank.register_leaf(event["event_id"], "agent_report", analysis,
                                   event["sequence"], "response", raw_sha)
                parsed = json.loads(observation)
                if not isinstance(parsed, dict) or set(parsed) != {"content", "tool_results"}:
                    raise ValueError("unknown GA observation envelope")
                bank.register_leaf(event["event_id"], "agent_report", parsed["content"],
                                   event["sequence"], "observation/content", raw_sha)
                if not isinstance(parsed["tool_results"], list):
                    raise ValueError("invalid GA tool results")
                for index, result in enumerate(parsed["tool_results"]):
                    if not isinstance(result, dict) or set(result) != {"tool_use_id", "content"}:
                        raise ValueError("unknown GA tool result envelope")
                    content = result["content"]
                    if not isinstance(content, str):
                        raise ValueError("unknown GA tool result content type")
                    base_path = f"observation/tool_results/{index}/content"
                    bank.register_leaf(event["event_id"], "tool_observation", content,
                                       event["sequence"], base_path, raw_sha)
                    # Decode only the GA tool-result envelope's documented text
                    # fields, once. Other JSON-looking strings are not guessed.
                    if content.startswith("{"):
                        try:
                            tool_payload = json.loads(content)
                        except json.JSONDecodeError:
                            tool_payload = None
                        if isinstance(tool_payload, dict) and "status" in tool_payload:
                            for field in ("stdout", "stderr", "msg", "output"):
                                value = tool_payload.get(field)
                                if isinstance(value, str) and value:
                                    bank.register_leaf(event["event_id"], "tool_observation",
                                        value, event["sequence"], base_path + "/" + field, raw_sha)
            else:
                bank.register_source(event["event_id"] + ":response", "agent_report",
                                     analysis, event["sequence"])
                bank.register_source(event["event_id"] + ":observation", "tool_observation",
                                     observation, event["sequence"])
            # Only handles actually present in the upstream task+window context
            # can be cited for a new assertion in this trigger.
            recent = self.agent._accumulated_observations[1:][
                -(self.agent._sliding_window_size - 1):]
            previous = [item.get("_source_event_id") for item in recent]
            bank.current_source_ids = [
                source_id for source_id in bank.sources
                if source_id == next(iter(bank.sources))
                or any(source_id.startswith(str(event_id) + ":") for event_id in previous)
                or source_id.startswith(event["event_id"] + ":")]
        self.agent._accumulate_step(step=step, observation=observation,
                                    analysis=analysis, plan=plan, commands=commands)
        if getattr(self.agent,'_memory_maintenance_policy',None) == 'pma-requirement-reminder-v1':
            self._requirement_entries.append({'step':step,'event_id':event['event_id'],
                'analysis':analysis,'plan':plan,'commands':commands,'observation':observation})
        if hasattr(self.agent._memory, "register_source"):
            self.agent._accumulated_observations[-1]["_source_event_id"] = event["event_id"]
        if getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1":
            from evidence_gap_context import event_identity
            self.agent._accumulated_observations[-1]["_evidence_identity"] = event_identity(event)
            if getattr(self.agent._memory_agent, 'review_strategy', None) == 'claim-split-same-evidence-v4':
                from pma_evidence_review.execution_link import inventory_from_accepted_event
                self.agent._accumulated_observations[-1]["_execution_inventory"] = inventory_from_accepted_event(event)
        triggered, reason = self.agent._trigger.should_trigger(step_count=step)
        if triggered:
            if getattr(self.agent,'_memory_maintenance_policy',None) == 'pma-requirement-reminder-v1':
                await self._run_requirement_reminder(step_count=step)
            elif getattr(self.agent, "_research_candidate", None) == "pma_gap_evidence_v1":
                from evidence_gap_context import prepare_context
                prepare_context(self.agent)
            elif getattr(self.agent, '_memory_maintenance_policy', None) == 'pma-bank-display-v1':
                self.agent._memory_agent.prepare_selection_context(
                    self.agent._get_memory_agent_context(),
                    self.agent._accumulated_observations[1:][-self.agent._sliding_window_size:])
            if getattr(self.agent,'_memory_maintenance_policy',None) != 'pma-requirement-reminder-v1':
                await self.agent._trigger_memory_agent(step_count=step)
        self.last_completed_attempt = attempt
        return {"status": "observed", "triggered": triggered,
                **({'memory_cycle_status':self._last_requirement_cycle_status} if triggered and hasattr(self,'_last_requirement_cycle_status') else {}),
                "trigger_reason": reason, "step_count": step}

    def _task_end(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self.started or self.ended or self.finalization_attempted:
            raise ValueError("task_end out of order")
        return self._save_final_state(event.get("terminal"), event)

    def _save_final_state(self, terminal: Any, event: dict[str, Any]) -> dict[str, Any]:
        """No-inference finalization; partial bank files never certify success."""
        self.finalization_attempted = True
        try:
            self.agent.save_memory(str(self.archive / "memory.json"))
            if not all((self.archive / name).is_file() for name in
                       ("memory.json", "trajectory_memory.json")):
                raise RuntimeError("upstream did not save both memory artifacts")
            for name in ("memory.json", "trajectory_memory.json"):
                with (self.archive / name).open("r", encoding="utf-8") as stream:
                    if not isinstance(json.load(stream), dict):
                        raise RuntimeError("upstream memory artifact is not an object")
        except Exception as exc:
            self._record(event, {"status": "save_failed", "error_type": type(exc).__name__,
                                 "terminal": terminal})
            raise
        return {"status": "saved", "terminal": terminal,
                "actor_attempts": self.last_attempt}

    def finalize_without_event(self, reason: str) -> dict[str, Any]:
        """Bounded host shutdown after ordinary Task event channel is unavailable."""
        if self.finalization_attempted or not self.started:
            return {"status": "not_saved", "reason": reason}
        result = self._save_final_state({"result": "TASK_TERMINAL_UNKNOWN"},
                                        {"kind": "host_finalize", "reason": reason})
        self.ended = True
        return {**result, "status": "saved_without_task_end", "reason": reason}
