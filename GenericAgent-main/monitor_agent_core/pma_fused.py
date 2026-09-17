"""Tool-enabled execution INSIDE the author's maintenance/comparison process.

Upstream owns phase sequencing, input construction and bank schemas/operations.
The monitor owns decision output: intervene, wait and allow_complete tools.
This adapter expands each model call into an investigation loop. It does not
run a third reviewer or clear the persistent monitor conversation between phases.
"""
import asyncio
import hashlib
from copy import deepcopy
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
If ready to propose intervene, wait or allow_complete, call that tool instead to
finish maintenance and carry the proposed action into judgment. Save needed bank
updates before this call. In this phase it only transfers intent: no task input,
waiting schedule or completion approval is executed. Judgment can confirm, revise
or discard the proposal using the updated bank and current evidence.
'''

PHASE_TWO = '''
You are now the judging and acting phase of that same persistent monitor, not an
adviser to a third reviewer. Investigate with ordinary tools whenever needed.
If investigation changes your grounds, use the same memory operations to revise
the bank here before continuing judgment. This is a return to maintenance within
the same investigation, not a second memory representation.
Use intervene to send a correction directly to the Task Agent.
After its submission receipt, keep observing understanding, intent and actions in this conversation;
correct further material drift when justified. Do not repeat an old correction blindly.
When no input is needed now, call wait with your chosen observation interval and mode.
That call ends this review immediately, not your history or the whole task.
There is no separate textual decision to emit before calling a control tool.
Use allow_complete only for a currently pending, justified root handoff, not merely
because no reminder is needed. Your checks must support the required behavior, not
just the presence of a similarly named artifact. Original requirements outrank memory.
'''

ROOT_DECISION = '''
You are deciding how to handle a current whole-task handoff, not whether a memory
reminder would be useful. Earlier reminder-selection questions do not govern this
decision. First interpret the actual handoff: a clarification or blocker is not
itself a claim of success.
For a completion claim, consider the original task as a whole. What must be true
to approve it, and what do the available observations actually establish?
Distinguish the agent's reports, your earlier beliefs, and observations with their
sources. A fixed local concern is not evidence that unrelated requirements hold.
If a material uncertainty could change this decision, briefly identify the concrete
question and seek the smallest useful observation with your existing tools. Ask
whether a plausible incorrect implementation would pass the same check. Choose
what to inspect yourself; neither a checklist nor a mandatory test command is needed.
Uncertainty can justify investigation without already proving an agent mistake.
Correct an evidenced deviation, or ask for needed clarification, without adding
requirements. Revise the same bank if your grounds change. Approve when evidence
is sufficient; do not chase every unknown or repeat checks ceremonially. If tools
cannot resolve a material gap, preserve it explicitly; exhaustion is not success.
Use the existing control tools and phase rules. This instruction neither grants
extra budget nor executes or approves a handoff on your behalf.
'''


def decision_prompts(system, prompt):
    """Retain author comparison guidance; replace its text-output contract once."""
    start, end = system.index('## OUTPUT FORMAT:'), system.index('## GUIDELINES:')
    system = (system[:start] + '## OUTPUT FORMAT:\n'
              'Use the available control tools: intervene sends input without ending investigation; '
              'wait ends this review and schedules observation; allow_complete handles a justified '
              'pending root completion. Plain text alone does not send input or end the review.\n\n'
              + system[end:])
    system = system.replace('<context_for_action>', 'intervene').replace('<no_intervention/>', 'wait')
    prompt = prompt.replace(
        'If yes, write a <context_for_action> note with the relevant context.\n'
        'If no, write <no_intervention/>.',
        'If yes, use intervene with the relevant context. If no input is needed now, use wait '
        'with your chosen interval and mode. For a pending root handoff, investigate and respond '
        'with intervene or allow_complete; absence of a reminder is not completion approval.')
    return system, prompt


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
                   author_result_is_control_projection=True, interventions=transport.interventions,
                   action=asdict(transport.action))
        return transport.action


class FusedTransport:
    def __init__(self, owner, monitor, tools):
        self.owner, self.monitor = owner, monitor
        self.tools = tools
        self.failure = None
        self.action = None
        self.calls = 0
        self.interventions = []
        self.pending_intent = None

    async def call(self, *, prompt, system, tools=None):
        if self.failure is not None:
            raise self.failure
        maintenance = tools is not None
        monitor, owner = self.monitor, self.owner
        phase = 'maintenance' if maintenance else 'comparison'
        if not maintenance:
            system, prompt = decision_prompts(system, prompt)
            if self.pending_intent is not None:
                prompt += ('\n\nMaintenance handed over the following proposed control action. '
                           'It has NOT been executed: no input sent, wait scheduled or completion approved. '
                           'Use the updated bank and current evidence to confirm, revise or discard it. '
                           'You may act now if its grounds still hold; no repeat investigation is required '
                           'just to change phases. Only a control tool in this phase executes the decision.\n'
                           + json.dumps(self.pending_intent, ensure_ascii=False))
                owner.audit('pma_control_intent_received', intent=self.pending_intent,
                            executed=False)
        bank_names = {t['function']['name'] for t in BANK_TOOLS}
        control_names = {'wait', 'allow_complete', 'intervene'}
        ordinary = deepcopy(self.tools)
        if maintenance:
            for tool in ordinary:
                function = tool['function']
                if function['name'] in control_names:
                    function['description'] = (
                        'Finish maintenance and hand this proposed action to judgment. '
                        'NOT executed here; judgment must confirm, revise or discard it. '
                        'Save memory updates before calling. In judgment this tool will: '
                        + function['description'])
        allowed = {t['function']['name'] for t in ordinary} | bank_names

        def dispatch(name, args):
            if name not in allowed:
                return ToolOutcome({'status': 'error', 'error': 'Tool unavailable in this phase'})
            if maintenance and name in control_names:
                if not isinstance(args, dict):
                    return ToolOutcome({'status': 'error', 'error': 'Tool arguments must be an object'})
                self.pending_intent = {'name': name, 'arguments': deepcopy(args)}
                receipt = {'status': 'intent_transferred', 'executed': False, 'input_sent': False,
                           'next': 'Judgment must confirm, revise or discard this proposal.'}
                owner.audit('pma_control_intent_handoff', intent=self.pending_intent, **receipt)
                return ToolOutcome(receipt, False, MonitorAction('maintenance_complete', {}))
            if name in bank_names:
                return owner.bank_call(name, args)
            outcome = monitor.dispatch(name, args)
            if name == 'intervene':
                submitted = ((outcome.data or {}).get('status') == 'submitted' or
                             (outcome.action is not None and outcome.action.kind == 'intervene'))
                if submitted:
                    self.interventions.append(args['message'])
                owner.audit('pma_direct_intervention', message=args.get('message'),
                            receipt=outcome.data, submitted=submitted,
                            action=asdict(outcome.action) if outcome.action else None)
            return outcome

        def text_result(text):
            if maintenance:
                if text.strip() == '<maintenance_complete/>':
                    return ToolOutcome(None, False, MonitorAction('maintenance_complete', {}))
                return ToolOutcome({'status': 'no_control_action', 'input_sent': False,
                                    'next': 'This is maintenance. No correction or silence was executed. '
                                    'Finish with <maintenance_complete/> to enter judgment; '
                                    'keep any concern in memory, not a claim of delivered intervention.'})
            return ToolOutcome({'status': 'no_control_action', 'input_sent': False,
                                'next': 'Use one control tool for your decision: intervene to send input; '
                                'wait to end this review; allow_complete for justified pending completion. '
                                'No extra investigation is required merely to restate a decision in the tool.'})

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
        system = system.replace('Track progress internally (not shown to action agent)',
                                'Maintain internal progress and its grounds')
        system = identity + '\n\n' + system + (PHASE_ONE if maintenance else PHASE_TWO)
        last_contract = None

        def current_system():
            nonlocal last_contract
            active = bool(monitor.completion_pending)
            proposal = getattr(monitor, '_seen_completion', None)
            generation = proposal.get('generation') if proposal else None
            contract = ('root' if active else 'ordinary', generation)
            selected = identity + '\n\n' + ROOT_DECISION + PHASE_TWO if active else system
            if contract != last_contract:
                owner.audit('root_decision_contract_selected', mode=contract[0],
                            generation=generation, phase=phase,
                            system_sha256=hashlib.sha256(selected.encode('utf-8')).hexdigest())
                last_contract = contract
            return selected

        dynamic_system = (current_system if monitor.root_decision_contract
                          and not maintenance else None)
        usage_start = len(getattr(monitor.client, 'usage_records', []))
        try:
            owner.audit('pma_fused_phase_started', phase=phase)
            action = run_review(monitor.client, system, prompt, ordinary + BANK_TOOLS,
                                dispatch, monitor.max_review_turns, audit=owner.audit,
                                before_model=before, on_text=text_result,
                                system_for_model=dynamic_system)
            if not maintenance:
                self.action = action
            # Operations were already executed through the author's executor and
            # receipts returned to the same model; never execute them twice.
            projection = ('<context_for_action>' + '\n\n'.join(self.interventions) + '</context_for_action>'
                          if self.interventions else '<no_intervention/>')
            return ModelResponse('<maintenance_complete/>' if maintenance else projection, [], {})
        except Exception as exc:
            self.failure = exc
            raise
        finally:
            for usage in getattr(monitor.client, 'usage_records', [])[usage_start:]:
                usage['monitor_phase'] = 'pma_fused_' + phase
