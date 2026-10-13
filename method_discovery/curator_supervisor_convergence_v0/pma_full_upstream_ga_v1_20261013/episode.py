"""Pilot-only event adapter around the unmodified upstream PMA object.

This module never starts Terminus2's actor loop.  Its actor backend is a
deliberately unusable BaseLLM; only the upstream memory LiteLLM may infer.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

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
                       memory_api_key: str | None = None) -> MemoryEnabledTerminus2:
    actor = DisabledActorLLM()
    agent = MemoryEnabledTerminus2(
        logs_dir=logs_dir, model_name="disabled-actor-not-ga-task-model",
        llm=actor, parser_name="xml", record_terminal_session=False,
        memory_model_name="openrouter/anthropic/claude-opus-4.6",
        memory_api_base=memory_api_base, memory_api_key=memory_api_key,
        memory_temperature=0.3, memory_max_thinking_tokens=None,
        memory_keep_thinking=False, memory_use_structured_tools=True,
        trigger_interval=1, trigger_on_first_step=True,
        sliding_window_size=8, reset_status_on_episode=True,
        reset_knowledge_on_episode=False, reset_procedural_on_episode=False,
        injection_method="user_turn",
    )
    if agent._llm is not actor:
        raise RuntimeError("upstream actor backend was not disabled")
    return agent


class PMAEpisode:
    """One task, one original object, one serial asyncio loop, no actor run."""

    def __init__(self, agent: MemoryEnabledTerminus2, *, run_id: str,
                 task_id: str, archive: Path):
        self.agent = agent
        self.run_id = run_id
        self.task_id = task_id
        self.archive = archive
        self.archive.mkdir(parents=True, exist_ok=False)
        self.started = False
        self.ended = False
        self.last_attempt = 0
        self.last_completed_attempt = 0
        self.last_sequence = 0
        self._responses: dict[str, tuple[str, dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    def _record(self, event: dict[str, Any], result: dict[str, Any]) -> None:
        line = json.dumps({"event": event, "result": result},
                          ensure_ascii=False, sort_keys=True)
        with (self.archive / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
            stream.flush()

    async def handle(self, event: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
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
            accepted_path = self.archive / "accepted.jsonl"
            with accepted_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event_id": event_id, "sequence": sequence,
                                         "sha256": digest}, sort_keys=True) + "\n")
                stream.flush()
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
            self._record(event, result)
            self.last_sequence = sequence
            self._responses[event_id] = (digest, result)
            return result

    async def _task_start(self, event: dict[str, Any]) -> dict[str, Any]:
        if self.started or self.ended:
            raise ValueError("task_start is only valid once")
        raw = event.get("initial_user_content")
        text = stable_initial_text(raw)
        self.agent._memory_step_in_episode = 0
        self.agent._trigger.reset()
        self.agent._accumulated_observations.clear()
        self.agent._pending_injection = None
        self.agent._injection_used = False
        self.agent._task_description = text
        if self.agent._reset_status_on_episode:
            self.agent._memory.update_status("")
        if self.agent._reset_knowledge_on_episode:
            self.agent._memory.knowledge.clear()
        if self.agent._reset_procedural_on_episode:
            self.agent._memory.procedural.clear()
        self.agent._accumulate_step(step=1, observation=text)
        triggered, reason = self.agent._trigger.should_trigger(step_count=1)
        self.started = True
        if triggered:
            await self.agent._trigger_memory_agent(step_count=1)
        return {"status": "started", "triggered": triggered, "trigger_reason": reason,
                "initial_envelope_sha256": hashlib.sha256(
                    json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}

    def _before_actor_call(self, event: dict[str, Any]) -> dict[str, Any]:
        attempt = event.get("actor_attempt")
        if not self.started or self.ended or type(attempt) is not int or attempt != self.last_attempt + 1:
            raise ValueError("non-monotonic actor attempt")
        self.agent._memory_step_in_episode = attempt
        self.last_attempt = attempt
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
        if not isinstance(analysis, str):
            raise ValueError("complete public actor response required")
        plan = event.get("plan")
        if plan is not None and not isinstance(plan, str):
            raise ValueError("plan must be text or absent")
        step = attempt + 1
        self.agent._accumulate_step(step=step, observation=observation,
                                    analysis=analysis, plan=plan, commands=commands)
        triggered, reason = self.agent._trigger.should_trigger(step_count=step)
        if triggered:
            await self.agent._trigger_memory_agent(step_count=step)
        self.last_completed_attempt = attempt
        return {"status": "observed", "triggered": triggered,
                "trigger_reason": reason, "step_count": step}

    def _task_end(self, event: dict[str, Any]) -> dict[str, Any]:
        if not self.started or self.ended:
            raise ValueError("task_end out of order")
        try:
            self.agent.save_memory(str(self.archive / "memory.json"))
        except Exception as exc:
            self._record(event, {"status": "save_failed", "error_type": type(exc).__name__})
            raise
        self.ended = True
        return {"status": "saved", "terminal": event.get("terminal"),
                "actor_attempts": self.last_attempt}
