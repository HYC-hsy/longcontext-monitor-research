"""Synchronous PMA protocol. No active inspection, interrupts or completion gate."""
import asyncio
from collections import deque
from dataclasses import asdict
import json
from pathlib import Path
import time
from types import SimpleNamespace

from .memory_agent import MemoryAgent


class PhaseClient:
    def __init__(self, factory):
        self.factory = factory
        self.attempts = []

    async def call(self, *, prompt, system, tools=None):
        # Upstream issues call(prompt=..., system=...), with the updated bank
        # explicitly rebuilt for phase 2. Do not add our persistent history.
        client = self.factory()
        record = {'started_at': time.time(), 'tools_enabled': bool(tools)}
        try:
            response = client.complete([
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': prompt}], tools or [])
            record['status'] = 'ok'
            return SimpleNamespace(content=response.content, tool_calls=[
                SimpleNamespace(function=SimpleNamespace(name=c.name, arguments=c.arguments))
                for c in response.tool_calls])
        except Exception as exc:
            record.update(status='failed', error_type=type(exc).__name__)
            raise
        finally:
            record['duration_seconds'] = time.time() - record['started_at']
            record['telemetry'] = client.drain_telemetry()
            self.attempts.append(record)


class PMABaseline:
    def __init__(self, task, llm, archive=None):
        self.task = str(task)
        self.llm = llm
        self.agent = MemoryAgent(llm=llm)
        self.steps = deque(maxlen=8)
        self.step = 0
        self.pending = None
        self.archive = Path(archive) if archive else None
        self.records = []

    def observe(self, analysis='', commands=(), observation=''):
        self.step += 1
        self.steps.append({'step': self.step, 'analysis': analysis,
                           'commands': list(commands), 'observation': observation})

    def context(self):
        parts = ['[Task Description]\n' + self.task]
        for entry in self.steps:
            parts.append(f"[Step {entry['step']}]\nAgent Analysis: {entry['analysis']}")
            commands = entry['commands']
            parts.append('Commands Executed: ' + '; '.join(commands[:5]) +
                         (f' (+{len(commands)-5} more)' if len(commands) > 5 else ''))
            parts.append('Terminal Output: ' + entry['observation'])
        return '\n\n'.join(parts)

    def review(self):
        started = time.time()
        before = len(getattr(self.llm, 'attempts', []))
        result = asyncio.run(self.agent.process(self.context(), step_count=self.step + 1))
        calls = getattr(self.llm, 'attempts', [])[before:]
        failed = any(c['status'] != 'ok' for c in calls)
        raw = result.raw_response_phase2 or ''
        recognized = bool(result.should_inject or '<no_intervention' in raw)
        status = 'provider_failure' if failed else (
            'reminder' if result.should_inject else 'no_intervention' if recognized else 'unrecognized_response')
        self.pending = result.context_for_action if result.should_inject else None
        record = {'step': self.step, 'started_at': started,
                  'duration_seconds': time.time() - started, 'status': status,
                  'result': asdict(result), 'phases': calls,
                  'bank': self.agent.memory.to_dict()}
        self.records.append(record)
        self._append('reviews.jsonl', record)

    def take_reminder(self):
        if not self.pending:
            return None
        note, self.pending = self.pending, None
        self._append('injections.jsonl', {'timestamp': time.time(), 'step': self.step,
                                        'status': 'returned_to_task_loop_not_behavioral_uptake'})
        return ('<memory_context>\nThe following context from memory may be relevant to your current work '
                '(these are observations, not directives — verify before acting):\n'
                + note + '\n</memory_context>')

    def _append(self, name, record):
        if self.archive:
            self.archive.mkdir(parents=True, exist_ok=True)
            with (self.archive / name).open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')


def from_environment(task):
    import os
    from llmcore import reload_mykeys
    from monitor_agent_core.provider import MonitorProviderClient
    if os.environ.get('GA_MONITOR_ENABLED') == '1':
        raise ValueError('PMA baseline and Clean Monitor are mutually exclusive')
    name = os.environ.get('GA_PMA_CONFIG', 'native_oai_cc_vibe_gpt56_sol_high')
    config = reload_mykeys()[0].get(name)
    if not config:
        raise ValueError('Unknown PMA model configuration')
    archive = os.environ.get('GA_PMA_ARTIFACT_DIR')
    if not archive:
        raise ValueError('PMA requires an explicit per-run artifact directory')
    return PMABaseline(task, PhaseClient(lambda: MonitorProviderClient(name, config)), archive)
