"""Run the unmodified PMA two-phase process inside the independent monitor.

Author code owns update/compare/reminder. The adapter owns provider transport,
public input mapping, persistence, audit and handoff to the existing review.
"""
import asyncio
from dataclasses import asdict
import json
import time

from .vendor.pma_memory.universal_memory import UniversalMemory
from .pma_observation import observation
from .pma_judgment import adapt, JudgmentMemoryAgent


class PhaseTransport:
    """Fresh author phase calls using the same provider and cancellation handle."""
    def __init__(self, client, understanding=None):
        self.client = client
        self.understanding = understanding
        self.records = []
        self.failure = None

    async def call(self, *, prompt, system, tools=None):
        if self.failure is not None:
            raise self.failure  # Do not spend another call after a failed phase.
        client = self.client
        history, previous_system = client.export_history(), client.system
        hooks = {name: getattr(client, name, None) for name in
                 ('prepare_active_context', 'prepare_continuation', 'archive_continuation_history')}
        phase = 'pma_memory_maintenance' if tools else 'pma_memory_comparison'
        record = dict(phase=phase, started_at=time.time(), status='failed')
        usage_start = len(getattr(client, 'usage_records', []))
        attempt_start = len(getattr(client, 'request_attempts', []))
        try:
            client.restore_history([])
            for name in hooks:
                setattr(client, name, None)
            adapted_system, adapted_tools = adapt(system, tools)
            initializing = bool(tools and self.understanding is not None and not self.understanding.read())
            if self.understanding is not None:
                adapted_system += ('\nKeep unresolved material grounds distinct from the latest repair. '
                                   'A monitor suggestion is local advice, not a replacement for the task. '
                                   'Do not turn compliance with it into proof of whole-task fulfillment.')
                prompt += '\n' + self.understanding.context()
                if initializing:
                    adapted_system += self.understanding.initialization_instruction()
            response = client.complete([
                {'role': 'system', 'content': adapted_system},
                {'role': 'user', 'content': prompt}], adapted_tools or [])
            record['usage'] = response.usage
            record['calls'] = [dict(name=c.name, arguments=c.arguments) for c in response.tool_calls]
            allowed = {t['function']['name'] for t in tools or []}
            if any(c.name not in allowed for c in response.tool_calls):
                raise RuntimeError('Unexpected PMA phase tool call')
            for call in response.tool_calls:
                if not isinstance(json.loads(call.arguments or '{}'), dict):
                    raise RuntimeError('PMA tool arguments must be an object')
            if initializing:
                self.understanding.capture(response.content)
                record['initial_task_model'] = self.understanding.draft
            record['status'] = 'ok'
            return response
        except Exception as exc:
            self.failure = exc
            record['error_type'] = type(exc).__name__
            raise
        finally:
            for item in getattr(client, 'usage_records', [])[usage_start:]:
                item['monitor_phase'] = phase
            for item in getattr(client, 'request_attempts', [])[attempt_start:]:
                item['monitor_phase'] = phase
            client.restore_history(history)
            client.system = previous_system
            for name, hook in hooks.items():
                setattr(client, name, hook)
            record['duration_seconds'] = time.time() - record['started_at']
            self.records.append(record)


class PMAMemoryMaintenance:
    def __init__(self, workspace, atomic_write, audit, understanding=None):
        self.workspace, self.atomic_write, self.audit = workspace, atomic_write, audit
        self.understanding = understanding
        self.path = workspace.private_root / 'pma_memory.json'
        self.memory = (UniversalMemory.from_dict(json.loads(self.path.read_text(encoding='utf-8')))
                       if self.path.exists() else UniversalMemory())
        self.author = JudgmentMemoryAgent(llm=None, memory=self.memory)
        self.query = ''
        self.cycle = 0

    def update(self, client, wake, review_id):
        started = time.time()
        self.query = observation(self.workspace, wake)
        self.cycle += 1
        before = self.memory.to_dict()
        record = dict(maintenance_id=review_id, started_at=started, before=before, status='failed')
        transport = PhaseTransport(client, self.understanding)
        self.author.llm = transport
        try:
            # Exact author execution entry: both prompts, operations, updated-bank
            # rebuilding and reminder parsing are inside MemoryAgent.process.
            result = asyncio.run(self.author.process(self.query, step_count=self.cycle))
            record['result'] = asdict(result)
            if transport.failure is not None:
                raise transport.failure
            if any(not op.success for op in result.operations):
                raise RuntimeError('PMA memory operation failed; see audit')
            raw = self.author._strip_thinking(result.raw_response_phase2 or '')
            if not result.should_inject and '<no_intervention' not in raw:
                raise RuntimeError('Unrecognized PMA comparison response')
            if self.understanding is not None:
                self.understanding.commit()
            self.atomic_write('pma_memory.json', json.dumps(self.memory.to_dict(), ensure_ascii=False))
            record['status'] = 'reminder' if result.should_inject else 'no_intervention'
            if result.should_inject:
                return ('Memory comparison produced this investigation lead, not a command or verdict. '
                        'Use your tools and current evidence to decide whether/how to act; the task may '
                        'have advanced since this comparison.\n' + result.context_for_action)
            return ('Memory comparison proposed no reminder. This is not completion approval or proof '
                    'of correctness. Continue your own review with its normal tools and responsibilities.')
        except Exception as exc:
            record['error_type'] = type(exc).__name__
            self.memory = UniversalMemory.from_dict(before)
            self.author.memory = self.memory
            if self.understanding is not None:
                self.understanding.draft = None
            raise
        finally:
            record['phases'] = transport.records
            record['after'] = self.memory.to_dict()
            record['duration_seconds'] = time.time() - started
            self.audit('pma_two_phase', **record)

    def context(self):
        return ('Revisable memory: entries are model judgments, not certified evidence. '
                'Original sources and your investigation tools remain available.\n'
                + self.author._format_memory_bank(self.query))
