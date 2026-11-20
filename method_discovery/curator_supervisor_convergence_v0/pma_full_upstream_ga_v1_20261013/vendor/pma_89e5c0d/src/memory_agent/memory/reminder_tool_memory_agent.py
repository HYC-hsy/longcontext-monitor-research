"""Native reminder tool, shared history/receipts, ordinary no-tool completion."""
import copy

from .read_context_predictive_memory_agent import (
    ReadContextPredictiveMemoryAgent, UnifiedMemoryAgentResult, MemoryOperation,
    PMAPhaseError, PMAToolRecoveryExhausted, PMADecisionRecoveryExhausted,
    MAX_CONSECUTIVE_TOOL_ERROR_ROUNDS, MAX_CONSECUTIVE_DECISION_ERROR_ROUNDS,
    PUBLIC_FORECAST_REMINDER, has_public_text,
)

REMINDER_TOOL_SYSTEM = """You are the task agent's information manager, helping it use existing information in long tasks. Your role is to draw on previously saved information to remind it when its work shows a disconnect between earlier and later steps, and to predict which information will be valuable for later work, then organize and save it.

The <task_description> tags contain the task agent's original task, and the <task_trajectory> tags contain the task agent's newly observed execution trajectory.

## Tools

- memory_add: Save information in the knowledge bank.
- memory_read: Read all information currently saved in the knowledge bank. Set bank_id to "knowledge" when calling it.
- send_reminder: Record information to remind the task agent of. All reminders successfully recorded during a wake are delivered in call order after that wake completes normally; none replaces an earlier reminder.

## Action Principles

- Before calling memory_add or send_reminder, briefly explain which information you selected and why.
- Before each call to send_reminder, first call memory_read to retrieve information from the knowledge bank.

Please manage task information in the following order:

1. Judge and decide the reminder. Use memory_read to review information previously saved in the knowledge bank. Consider the newly observed execution trajectory. When the task agent's work shows a disconnect between earlier and later steps, use send_reminder to bring both the disconnect and the relevant earlier and later information back to its attention, so it can revisit, check, and address the issue.

2. Predict and save. After deciding whether to remind the task agent, you must predict which information from the original task description and the newly observed execution trajectory will still be worth presenting to the task agent to support subsequent work after the task has progressed for another eight turns. Use memory_add to organize, restate, and save the selected information and necessary context in the knowledge bank, so that the task agent can accurately understand what the original materials conveyed at the time even when it can no longer see them.
"""

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
