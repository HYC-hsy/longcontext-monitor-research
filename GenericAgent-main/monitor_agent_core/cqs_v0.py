"""Control continuity from this Supervisor's executed actions, without semantic extraction."""

from __future__ import annotations

import hashlib
import json


MAX_CHARS = 1400
MESSAGE_CHARS = 300
RATIONALE_CHARS = 280


def _excerpt(value, limit):
    value = str(value or '').strip()
    return value[:limit] + (' [excerpt truncated]' if len(value) > limit else '')


def _hash(value):
    return hashlib.sha256(str(value or '').encode('utf-8')).hexdigest()


class ControlQuestionState:
    """One current action-derived concern, not a task-status or requirement ledger."""

    def __init__(self, audit):
        self.audit = audit
        self.state = None
        self.review_id = None
        self.last_output = None
        self.last_call = None
        self.pending_surface = None

    def begin_review(self, review_id):
        self.review_id = review_id
        self.last_output = None
        self.last_call = None
        self.pending_surface = None

    def observe(self, record, line):
        if record.get('review_id') != self.review_id:
            return
        locator = f'monitor/audit/dialogue.jsonl#{line}'
        if record.get('event') == 'model_output' and str(record.get('content') or '').strip():
            self.last_output = {'text': record['content'], 'locator': locator,
                                'model_turn': record.get('turn')}
        elif record.get('event') == 'tool_call':
            try:
                arguments = json.loads(record.get('arguments') or '{}')
            except (ValueError, TypeError):
                arguments = {}
            self.last_call = {'name': record.get('name'), 'arguments': arguments,
                              'locator': locator, 'model_turn': record.get('turn')}

    def _replace(self, source, control_text, action_locator=None, model_turn=None,
                 after_turns=None):
        rationale = self.last_output or {}
        call = self.last_call or {}
        state = {
            'active': True, 'source': source,
            'control_excerpt': _excerpt(control_text, MESSAGE_CHARS),
            'control_sha256': _hash(control_text),
            'rationale_excerpt': _excerpt(rationale.get('text'), RATIONALE_CHARS),
            'rationale_sha256': _hash(rationale.get('text')),
            'rationale_locator': rationale.get('locator'),
            'action_locator': action_locator or call.get('locator'),
            'review_id': self.review_id,
            'model_turn': model_turn if model_turn is not None else call.get('model_turn'),
            'after_turns': after_turns,
        }
        self.state = state
        self.audit('cqs_state_updated', **{k: v for k, v in state.items() if k != 'review_id'})

    def submitted_intervention(self, message):
        call = self.last_call or {}
        self._replace('intervene', message, action_locator=call.get('locator'),
                      model_turn=call.get('model_turn'))

    def completed_wait(self, action):
        if action.kind != 'wait':
            return
        call = self.last_call or {}
        args = call.get('arguments', {}) if call.get('name') == 'wait' else {}
        if action.payload.get('mode') == 'follow':
            self._replace('wait_follow', args.get('reason'),
                          action_locator=call.get('locator'),
                          model_turn=call.get('model_turn'),
                          after_turns=action.payload.get('after_turns'))
        elif action.payload.get('mode') == 'patrol':
            previous = self.state
            self.state = None
            self.audit('cqs_state_cleared', active=False, source_action='wait_patrol',
                       previous_source=previous.get('source') if previous else None,
                       model_turn=call.get('model_turn'),
                       action_locator=call.get('locator'))

    def render(self):
        lines = [
            'Supervisory Control Continuity — your own prior control context, not verified task truth.',
            'Governing objective: the full public task at task/original_task.txt remains authoritative; '
            'this continuity state does not replace it.',
        ]
        if self.state is None:
            lines.append('No active concern is carried from the prior control action. Choose what matters now '
                         'from the governing public task and current evidence; absence of an active concern '
                         'is not a whole-task completion verdict.')
        else:
            source = self.state['source']
            lines.append('Last control: ' + ('submitted intervention' if source == 'intervene'
                                             else 'wait(mode=follow)') + '.')
            if self.state['control_excerpt']:
                lines.append(('Submitted message: ' if source == 'intervene' else 'Follow reason: ') +
                             self.state['control_excerpt'])
            if self.state['rationale_excerpt']:
                lines.append('Prior natural rationale: ' + self.state['rationale_excerpt'])
            lines.append('Source: ' + str(self.state['action_locator'] or 'locator unavailable') +
                         '; rationale: ' + str(self.state['rationale_locator'] or 'none recorded') + '.')
            lines.append('Use current public feedback to continue, revise, or retire this concern. '
                         'Resolving it establishes only what its grounds support; this state is not '
                         'a target-completion ledger.')
        content = '\n'.join(lines)
        if len(content) > MAX_CHARS:
            raise ValueError('CQS bounded representation exceeded')
        self.pending_surface = {'content': content, 'state_source':
                                self.state.get('source') if self.state else None,
                                'active': self.state is not None}
        return content

    def surface_visible(self):
        shown = self.pending_surface
        self.pending_surface = None
        if shown is not None:
            self.audit('cqs_surface_emitted', **shown,
                       rendered_char_count=len(shown['content']))
        return shown
