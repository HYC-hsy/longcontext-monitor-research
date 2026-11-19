"""Native reminder tool, shared history/receipts, ordinary no-tool completion."""
import copy

from .read_context_predictive_memory_agent import (
    ReadContextPredictiveMemoryAgent, UnifiedMemoryAgentResult, MemoryOperation,
    PMAPhaseError, PMAToolRecoveryExhausted, PMADecisionRecoveryExhausted,
    MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS, MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS,
    PUBLIC_FORECAST_REMINDER, has_public_text, REMIND_FIRST_SYSTEM,
)

REMINDER_TOOL_SYSTEM = REMIND_FIRST_SYSTEM.replace(
    '- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.',
    '- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.\n'
    '- send_reminder: Record information to remind the task agent of. All reminders successfully recorded during a wake are delivered in call order after that wake completes normally; none replaces an earlier reminder.'
).replace(
    'Express the reminder decision with one of:\n<context_for_action>\nInformation to remind the task agent of.\n</context_for_action>\n<no_intervention/>',
    'If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.'
).replace(
    '- Before expressing the reminder decision, briefly explain your judgment.\n'
    '- Before calling memory_add, briefly state which information you have selected.',
    '- Before each tool call, you must use one or two sentences to explain your '
    'judgment, the available information on which it is based, and the extent to '
    'which that information supports it. When calling memory_add, also state which '
    'information you have selected.'
).replace(
    'Manage task information through the following steps:',
    'Please manage task information in the following order:'
).replace(
    '- When saving, fully retain the content needed to understand and use the selected information later.',
    '- When saving, use the selected original information fragments as material to '
    'organize and summarize, preserving their original meaning and current state, '
    'as well as the context needed to understand and use them later.\n'
    '- Before each call to send_reminder, first call memory_read to '
    'retrieve information from the knowledge bank.'
).replace(
    "2. Predict and save. Based on the task description, the task agent's trajectory, and the"
    ' judgment you have just made, you must predict which information received this time will'
    ' still be worth presenting to the task agent to support subsequent task work after the '
    'task has progressed for another eight turns, and organize and save that information in '
    'the knowledge bank.',
    "2. Predict and save. Pieces of information affect one another's value. After completing "
    "the reminder decision, based on the task description, the task agent's execution "
    'trajectory, and the judgment and reminder decision you have just made, you must predict '
    'which fragments of the original information received this time will still be worth '
    'presenting to the task agent to support subsequent task work after the task has '
    'progressed for another eight turns. Organize and summarize the selected fragments '
    'together with the context needed to understand them, and save them in the knowledge bank as memories whose origins are clear and that can be revised in light of new information.'
).replace(
    "1. Judge and decide the reminder. You must use memory_read to carefully review the existing knowledge bank. After receiving its result, consider the task agent's execution trajectory. You must judge which information in the knowledge bank, as the task progresses, has become valuable or remains valuable for the task agent's current or upcoming work, and accordingly decide whether to remind the task agent and what to remind it of. If a reminder is needed, call send_reminder with its content. Otherwise, do not call it.",
    "1. Judge and decide the reminder. As the task agent's external memory, you must use memory_read to review the existing knowledge bank and consider the task agent's execution trajectory to judge which stored information is valuable for its current or upcoming work, and accordingly decide whether to remind it and what to remind it of. If a reminder is needed, use send_reminder to bring all of the selected information and the necessary context back into the task agent's view, so it can continue making judgments and carrying the task forward. Otherwise, do not call it."
)

REMINDER_TOOL = {
    'type': 'function', 'function': {
        'name': 'send_reminder',
        'description': 'Record a reminder for the task agent. All reminders successfully recorded during a wake are delivered in call order after that wake completes normally; none replaces an earlier reminder. This call does not deliver them immediately.',
        'parameters': {'type': 'object', 'properties': {
            'content': {'type': 'string', 'description': 'The complete reminder text for the task agent. It may include original text, code, or formulas.'}
        }, 'required': ['content'], 'additionalProperties': False},
    },
}


def is_wake_completion(response):
    if getattr(response, 'tool_calls', None):
        return False
    raw = getattr(response, 'content', None)
    if not isinstance(raw, str) or not has_public_text(raw):
        return False
    if any(marker in raw[-100:] for marker in ('[!!! 流异常中断', '!!!Error:', 'max_tokens !!!]')):
        return False
    return not any(getattr(response, key, None) in {'length', 'max_tokens', 'error'}
                   for key in ('finish_reason', 'stop_reason'))


class ReminderToolMemoryAgent(ReadContextPredictiveMemoryAgent):
    """Prompt-guided order, with every tool available throughout a wake."""

    def reset_conversation_history(self):
        super().reset_conversation_history()
        self._recorded_reminders = []

    def get_tools_schema(self):
        return super().get_tools_schema() + [copy.deepcopy(REMINDER_TOOL)]

    def _record_reminder(self, args):
        if set(args) != {'content'}:
            raise ValueError('send_reminder accepts only content')
        content = args['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('reminder content must be nonempty text')
        self._recorded_reminders.append(content)
        return MemoryOperation(action='send_reminder', content=content)

    async def process(self, observation, step_count=0):
        self._step = step_count
        self._unified_rounds = []
        self._phase1_operations = []
        self._recorded_reminders = []
        try:
            prompt = self._build_phase1_prompt(observation, step_count)
            response = await self._call_llm_phase1(prompt)
            return UnifiedMemoryAgentResult(
                operations=list(self._phase1_operations),
                should_inject=bool(self._recorded_reminders),
                context_for_action='\n\n'.join(self._recorded_reminders) if self._recorded_reminders else None,
                raw_response_phase1=getattr(response, 'content', None) or '',
                user_prompt_phase1=prompt, loop_mode='reminder_tool',
                loop_rounds=copy.deepcopy(self._unified_rounds), termination='wake_no_tool')
        except Exception as exc:
            raise PMAPhaseError('unified', exc) from exc

    async def _call_llm_phase1(self, user_prompt):
        prior = self._p1_prior(user_prompt, new_wake=True)
        self._new_trajectory = None
        error_rounds = empty_rounds = 0
        while True:
            system = REMINDER_TOOL_SYSTEM
            if self._p1_public_text_missing:
                system += '\n\n' + PUBLIC_FORECAST_REMINDER
            response = await self.llm.call(prompt=user_prompt, system=system,
                tools=self.get_tools_schema(), message_history=prior)
            operations, _ = self._record_p1_response(response)
            self._phase1_operations.extend(operations)
            raw = getattr(response, 'content', None) or ''
            if any(op.action == 'add' for op in operations):
                self._p1_public_text_missing = not has_public_text(raw)
            elif has_public_text(raw):
                self._p1_public_text_missing = False
            failed = any(not operation.success for operation in operations)
            completed = is_wake_completion(response)
            self._unified_rounds.append({
                'round': len(self._unified_rounds) + 1, 'stage': 'manage',
                'prompt': user_prompt, 'content': raw,
                'operation_count': len(operations), 'tool_error': failed,
                'reminders_recorded': len(self._recorded_reminders),
                'wake_completed': completed})
            if completed:
                return response
            error_rounds = error_rounds + 1 if failed else 0
            empty_rounds = empty_rounds + 1 if not operations else 0
            if error_rounds >= MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS:
                raise PMAToolRecoveryExhausted(f'{error_rounds} consecutive tool-error rounds')
            if empty_rounds >= MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS:
                raise PMADecisionRecoveryExhausted(f'{empty_rounds} invalid no-tool responses')
            user_prompt = (
                'Review the tool receipts and correct failed calls if needed. Do not repeat successful calls.'
                if failed else 'Continue.' if operations else
                'No valid completion was received. Continue if needed, or finish with ordinary text without tool calls.')
            prior = self._p1_prior(user_prompt, new_wake=False)
