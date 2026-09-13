"""Tool-enabled execution INSIDE the author's maintenance/comparison process.

Upstream owns prompts, bank schemas/operations, formatting and reminder parsing.
This adapter expands each model call into an investigation loop. It does not
run a third reviewer or clear the persistent monitor conversation between phases.
"""
import asyncio
from dataclasses import asdict
import json

from .actions import MonitorAction, ToolOutcome
from .loop import run_review, MonitorLoopError
from .pma_observation import observation
from .provider import ModelResponse, ToolCall
from .vendor.pma_memory.memory_agent import MemoryAgent, BANK_TOOLS
from .vendor.pma_memory.universal_memory import UniversalMemory


PHASE_ONE = '''
You are performing the maintenance phase of the persistent monitor, not writing advice
for another reviewer. Use ordinary investigation tools when more evidence matters.
Update the bank with the provided memory operations. Distinguish requirements, claims,
observations and their scope; saved conclusions remain revisable. The bank is your
durable cognition; private files are optional supporting material, not required parallel
progress reports. When maintenance is sufficient, respond <maintenance_complete/>.
Do not send task input or decide root completion in this phase.
'''

PHASE_TWO = '''
You are now the judging and acting phase of that same persistent monitor, not an
adviser to a third reviewer. Investigate with ordinary tools whenever needed.
If investigation changes your grounds, use the same memory operations to revise
the bank here before continuing judgment. This is a return to maintenance within
the same investigation, not a second memory representation.
Your <context_for_action> text is sent directly to the Task Agent as user input.
After sending it, keep observing understanding, intent and actions in this conversation;
correct further material drift when justified. Do not repeat an old correction blindly.
<no_intervention/> sends nothing; then choose when to observe next with wait.
Use allow_complete only for a currently pending, justified root handoff, not merely
because no reminder is needed. Your checks must support the required behavior, not
just the presence of a similarly named artifact. Original requirements outrank memory.
'''


class FusedPMA:
    def __init__(self, workspace, atomic_write, audit):
        self.workspace, self.atomic_write, self.audit = workspace, atomic_write, audit
        self.path = workspace.private_root / 'pma_memory.json'
        self.memory = (UniversalMemory.from_dict(json.loads(self.path.read_text(encoding='utf-8')))
                       if self.path.exists() else UniversalMemory())
        self.author = MemoryAgent(llm=None, memory=self.memory)
        self.query = ''
        self.cycle = 0

    def context(self):
        return 'Current revisable memory, not certified evidence:\n' + self.author._format_memory_bank(self.query)

    def bank_call(self, name, arguments):
        before = self.memory.to_dict()
        response = ModelResponse('', [ToolCall('bank', name, json.dumps(arguments))], {})
        operations = self.author._execute_tool_calls(response)
        try:
            if not operations or any(not op.success for op in operations):
                raise ValueError('; '.join(op.error or 'operation failed' for op in operations))
            self.atomic_write('pma_memory.json', json.dumps(self.memory.to_dict(), ensure_ascii=False))
        except Exception as exc:
            self.memory = UniversalMemory.from_dict(before)
            self.author.memory = self.memory
            self.audit('pma_bank_operation', name=name, operations=[asdict(o) for o in operations],
                       status='failed', error_type=type(exc).__name__)
            return ToolOutcome({'status': 'error', 'error': str(exc)})
        self.audit('pma_bank_operation', name=name, operations=[asdict(o) for o in operations], status='ok')
        return ToolOutcome({'status': 'ok', 'operations': [asdict(o) for o in operations]})

    def review(self, monitor, wake, tools):
        self.cycle += 1
        self.query = observation(self.workspace, wake, include_monitor_receipts=False)
        self.query += '\nLive environment map (task sources read-only; private cognition writable):\n' + json.dumps({
            'task/': str(self.workspace.evidence_root),
            **{f'task/{name}/': str(path) for name, path in self.workspace.task_mounts.items()},
            'monitor/': str(self.workspace.private_root)}, ensure_ascii=False)
        transport = FusedTransport(self, monitor, tools)
        self.author.llm = transport
        # Author process rebuilds phase two from the bank updated by phase one.
        result = asyncio.run(self.author.process(self.query, step_count=self.cycle))
        if transport.failure is not None:
            raise transport.failure  # Upstream catches phase errors; do not hide them.
        if transport.action is None:
            raise MonitorLoopError('Fused comparison ended without a monitor control action')
        self.audit('pma_fused_cycle', result=asdict(result), model_calls=transport.calls,
                   action=asdict(transport.action))
        return transport.action


class FusedTransport:
    def __init__(self, owner, monitor, tools):
        self.owner, self.monitor = owner, monitor
        self.tools = tools
        self.failure = None
        self.action = None
        self.calls = 0

    async def call(self, *, prompt, system, tools=None):
        if self.failure is not None:
            raise self.failure
        maintenance = tools is not None
        monitor, owner = self.monitor, self.owner
        phase = 'maintenance' if maintenance else 'comparison'
        bank_names = {t['function']['name'] for t in BANK_TOOLS}
        ordinary = [t for t in self.tools if t['function']['name'] not in
                    ({'wait', 'allow_complete', 'intervene'} if maintenance else {'intervene'})]
        allowed = {t['function']['name'] for t in ordinary} | bank_names

        def dispatch(name, args):
            if name not in allowed:
                return ToolOutcome({'status': 'error', 'error': 'Tool unavailable in this phase'})
            if name in bank_names:
                return owner.bank_call(name, args)
            return monitor.dispatch(name, args)

        def text_result(text):
            if maintenance:
                if text.strip() == '<maintenance_complete/>':
                    return ToolOutcome(None, False, MonitorAction('maintenance_complete', {}))
                return ToolOutcome({'next': 'Investigate or update memory as needed; finish with <maintenance_complete/>.'})
            reminder = owner.author._parse_phase2_response(text)
            if reminder:
                outcome = monitor.dispatch('intervene', {'message': reminder})
                owner.audit('pma_direct_intervention', message=reminder, receipt=outcome.data,
                            action=asdict(outcome.action) if outcome.action else None)
                return outcome
            return ToolOutcome({'next': 'No input sent. Continue investigating or use wait; assess a pending handoff explicitly.'})

        def before():
            self.calls += 1
            if self.calls > monitor.max_review_turns:
                raise MonitorLoopError('Fused review exhausted its shared model-call budget')
            return monitor._refresh_review_context()

        # Stable identity and control principles are shared. Author phase role and
        # output formats are preserved, with explicit tool/control adaptation.
        identity = monitor.system_prompt
        identity = identity.replace('Keep monitor/working.md as your revisable understanding',
                                    'Use the memory bank as your revisable understanding')
        identity = identity.replace('Use intervene\ndirectly', 'Send <context_for_action>\ndirectly')
        system = system.replace('Track progress internally (not shown to action agent)',
                                'Maintain internal progress and its grounds')
        system = identity + '\n\n' + system + (PHASE_ONE if maintenance else PHASE_TWO)
        usage_start = len(getattr(monitor.client, 'usage_records', []))
        try:
            owner.audit('pma_fused_phase_started', phase=phase)
            action = run_review(monitor.client, system, prompt, ordinary + BANK_TOOLS,
                                dispatch, monitor.max_review_turns, audit=owner.audit,
                                before_model=before, on_text=text_result)
            if not maintenance:
                self.action = action
            # Operations were already executed through the author's executor and
            # receipts returned to the same model; never execute them twice.
            return ModelResponse('<maintenance_complete/>' if maintenance else '<no_intervention/>', [], {})
        except Exception as exc:
            self.failure = exc
            raise
        finally:
            for usage in getattr(monitor.client, 'usage_records', [])[usage_start:]:
                usage['monitor_phase'] = 'pma_fused_' + phase
