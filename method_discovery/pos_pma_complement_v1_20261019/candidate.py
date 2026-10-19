"""Default-off PoS/PMA candidate core; original upstream state and bank are retained."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from citation_fix import CitationFixedBeliefManager, CitationFixedSentinel


LIMITS = {'task_panel_chars': 16000, 'phase2_advisory_chars': 16000,
          'revision_chars': 12000, 'history_events': 4,
          'history_event_chars': 2000, 'related_records': 8}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


class CandidateRoleTransportFailure(Exception):
    """Do not let released PoS treat a failed role transport as a rejected idea."""


class CandidateSentinel(CitationFixedSentinel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_format_rejection = None

    def audit_candidate(self, **kwargs):
        self.last_format_rejection = None
        try:
            return super().audit_candidate(**kwargs)
        except RuntimeError as error:
            # Released manager intentionally retains the old state here.
            # Preserve that behavior, but expose the protocol outcome.
            self.last_format_rejection = type(error).__name__
            raise


class ComplementBeliefManager(CitationFixedBeliefManager):
    """Only candidate inputs and post-commit text projection differ from PoS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.sentinel is not None:
            prior = self.sentinel
            self.sentinel = CandidateSentinel(prior.config, prior.call_model,
                prior.logger, call_progress_model=prior.call_progress_model)
        self.revision_context = ''

    def _request_candidate(self, messages, *, base, operation, step):
        if self.revision_context and operation in {'update', 'sentinel_repair'}:
            messages = [dict(item) for item in messages]
            messages[1]['content'] += ('\n\nCandidate-only revision context: this is a '
                'previously delivered, fallible PMA suggestion, not a tool result '\
                'or a Sentinel finding. Test it against the actual transition:\n' +
                self.revision_context)
        return super()._request_candidate(messages, base=base,
                                          operation=operation, step=step)

    def _refresh_belief_text(self, *, step):
        context = self._structured_context()
        snapshot = {key: context.get(key) for key in
                    ('goal', 'epistemic_gaps', 'achievement_gaps', 'frontier_gap')}
        self._current().belief_text = _json(snapshot)
        self.logger.log('belief_text_updated', case_id=self.case_id, step=step,
                        belief_text=self._current().belief_text,
                        origin='deterministic_committed_fields_v1')


def _gap_records(context):
    gaps = [*context.get('epistemic_gaps', []), *context.get('achievement_gaps', [])]
    frontier = context.get('frontier_gap')
    ids = []
    if isinstance(frontier, dict) and isinstance(frontier.get('target'), str):
        ids.append(frontier['target'])
    for gap in gaps:
        target = gap.get('target') if isinstance(gap, dict) else None
        if isinstance(target, str) and target not in ids:
            ids.append(target)
    world = context.get('world', {})
    selected = []
    for identifier in ids:
        for kind in ('entities', 'states', 'relations'):
            records = world.get(kind, {})
            if identifier in records:
                selected.append({'kind': kind, 'id': identifier,
                                 'record': deepcopy(records[identifier])})
                break
        if len(selected) == LIMITS['related_records']:
            break
    return selected


def _required_state(context, *, include_recovery=False):
    state = {'state_version': context.get('step'),
            'goal': context.get('goal'),
            'epistemic_gaps': context.get('epistemic_gaps', []),
            'achievement_gaps': context.get('achievement_gaps', []),
            'frontier_gap': context.get('frontier_gap'),
            'model_tags_are_not_external_verification': True}
    if include_recovery:
        state['recovery_signal'] = context.get('recovery')
    return state


def render_task_panel(context, *, advice=None, original_observation=None):
    """A transient system suffix, never a new user instruction or session history."""
    required = _required_state(context)
    head = ('Auxiliary model-generated current-state view; may be wrong. '
            'This is not a new user requirement, tool receipt, completion gate or '
            'authorization. The original Task and actual observations remain authoritative.\n')
    body = head + _json(required)
    if len(body) > LIMITS['task_panel_chars']:
        raise ValueError('required current goal/gaps exceed Task panel budget')
    omitted = []
    for record in _gap_records(context):
        part = '\n\nDirectly related model-state record:\n' + _json(record)
        if len(body) + len(part) <= LIMITS['task_panel_chars']:
            body += part
        else:
            omitted.append('related_record:' + record['id'])
    if original_observation:
        observation_part = 'Latest actual observation (host source):\n' + str(original_observation)
        if len(body) + len(observation_part) + 2 <= LIMITS['task_panel_chars']:
            body += '\n\n' + observation_part
        else:
            # The actual receipt is still in ordinary GA history. This panel
            # must not pretend that a clipped excerpt is the full receipt.
            omitted.append('latest_observation_panel_copy')
            marker = '\n\nLatest actual observation remains in GA history (panel omitted).'
            if len(body) + len(marker) <= LIMITS['task_panel_chars']:
                body += marker
    included_advice = None
    if advice:
        if not isinstance(advice, str):
            raise TypeError('advice must be plain text')
        proposed = 'Tentative PMA suggestion, not a fact or command:\n' + advice
        if len(body) + len(proposed) + 2 <= LIMITS['task_panel_chars']:
            body += '\n\n' + proposed
            included_advice = advice
        else:
            omitted.append('advice')
    return {'panel': body, 'panel_sha256': _digest(body),
            'included_advice': included_advice,
            'advice_sha256': _digest(included_advice) if included_advice else None,
            'budget_suppressed': bool(advice and included_advice is None),
            'omitted': omitted}


def revision_packet(*, delivered, completed_transition_id, source_events):
    """Only a sent suggestion plus an actual later transition can be revisited."""
    if not delivered or not completed_transition_id:
        return ''
    excerpts = []
    for item in [item for item in source_events if item][:LIMITS['history_events']]:
        raw = _json(item)
        limit = LIMITS['history_event_chars']
        if len(raw) > limit:
            half = max(0, (limit - 40) // 2)
            raw = raw[:half] + '\n[TRUNCATED; NOT A CITABLE SOURCE]\n' + raw[-half:]
        excerpts.append({'host_receipt_excerpt': raw,
                         'full_receipt_sha256': _digest(_json(item))})
    packet = {'origin': 'pma_tentative_suggestion',
              'generated_state_version': delivered['state_version'],
              'delivery_event_id': delivered['delivery_event_id'],
              'suggestion': delivered['advice'],
              'completed_transition_id': completed_transition_id,
              'source_events': excerpts}
    result = _json(packet)
    if len(result) > LIMITS['revision_chars']:
        raise ValueError('revision context exceeds candidate budget')
    return result


class ComplementEpisode:
    """One PoS graph, one PMA bank, one advice cursor per fresh Task episode."""

    def __init__(self, *, pos_episode, memory_agent, trigger, logger):
        self.pos = pos_episode
        self.manager = pos_episode.manager
        self.case_id = pos_episode.case_id
        self.memory = memory_agent
        self.trigger = trigger
        self.logger = logger
        self.pending_advice = None
        self.delivered = None
        self.started = False
        self.ended = False
        self.events = []
        self.original_task = ''
        self.recent_steps = []

    def _pma_observation(self):
        """Original PMA task + eight actor-step window, without PoS prose."""
        parts = [f'[Task Description]\n{self.original_task}']
        window = self.recent_steps[-8:]
        if window:
            parts.append(f'[Recent Trajectory (last {len(window)} steps)]')
            for item in window:
                sections = [f"[Step {item['step']}]"]
                if item['analysis']:
                    sections.append('Agent Analysis: ' + item['analysis'])
                if item['commands']:
                    commands = item['commands']
                    command_text = '; '.join(commands[:5])
                    if len(commands) > 5:
                        command_text += f' (+{len(commands) - 5} more)'
                    sections.append('Commands Executed: ' + command_text)
                sections.append('Terminal Output: ' + item['observation'])
                parts.append('\n'.join(sections))
        return '\n\n'.join(parts)

    async def reset(self, *, task, observation, actions):
        if self.started:
            raise RuntimeError('candidate already initialized')
        if self.memory.memory.status or self.memory.memory.knowledge or self.memory.memory.procedural:
            raise ValueError('candidate requires a fresh empty PMA bank')
        self.pos.reset(task=task, observation=observation, actions=actions)
        if (self.manager.sentinel is not None and
                self.manager.sentinel.last_format_rejection):
            raise RuntimeError('candidate initialization audit format rejected')
        self.started = True
        self.original_task = task
        self.trigger.reset()
        triggered, reason = self.trigger.should_trigger(1)
        if triggered:
            result = await self.memory.process(self._pma_observation(), 1,
                advisory_context=self._phase2_context())
            self.pending_advice = result.context_for_action
        self.events.append({'kind': 'reset', 'triggered': triggered, 'reason': reason,
                            'phase2_status': self.memory.last_phase2_status if triggered else None})
        return self.decision_panel(observation=observation)

    def _phase2_context(self):
        context = self.pos.get_context()
        required = _required_state(context, include_recovery=True)
        value = _json(required)
        if len(value) > LIMITS['phase2_advisory_chars']:
            raise ValueError('required PoS state exceeds Phase 2 advisory budget')
        for record in _gap_records(context):
            part = '\nDirectly related model-state record: ' + _json(record)
            if len(value) + len(part) <= LIMITS['phase2_advisory_chars']:
                value += part
            else:
                self.events.append({'kind': 'phase2_optional_omitted',
                                    'record_id': record['id']})
        return value

    def decision_panel(self, *, observation):
        if not self.started or self.ended:
            raise RuntimeError('candidate not active')
        result = render_task_panel(self.pos.get_context(),
            advice=self.pending_advice, original_observation=observation)
        self.events.append({'kind': 'panel_prepared',
                            'panel_sha256': result['panel_sha256'],
                            'advice_sha256': result['advice_sha256'],
                            'budget_suppressed': result['budget_suppressed']})
        return result

    def request_accepted(self, *, panel, event_id):
        """Conservative receipt: never infer delivery from mere panel preparation."""
        if not self.started or self.ended or not event_id:
            raise ValueError('accepted request identity required')
        if panel.get('included_advice'):
            self.delivered = {'advice': panel['included_advice'],
                'state_version': self.pos.get_context().get('step'),
                'delivery_event_id': event_id,
                'panel_sha256': panel['panel_sha256']}
        self.events.append({'kind': 'request_accepted', 'event_id': event_id,
                            'panel_sha256': panel['panel_sha256']})

    async def update(self, *, actor_attempt, transition_id, thought,
                     action_batch, observation, source_events=(), done=False):
        if not self.started or self.ended:
            raise RuntimeError('candidate not active')
        if not action_batch:
            raise ValueError('candidate update requires a real joint-action batch')
        revision = revision_packet(delivered=self.delivered,
            completed_transition_id=transition_id, source_events=source_events)
        manager = self.pos.manager
        manager.revision_context = revision
        try:
            self.pos.update(thought=thought, action_batch=action_batch,
                            observation=observation, done=done)
        finally:
            manager.revision_context = ''
        if (manager.sentinel is not None and
                manager.sentinel.last_format_rejection):
            self.events.append({'kind': 'pos_format_rejected',
                                'transition_id': transition_id,
                                'reason': manager.sentinel.last_format_rejection})
        self.events.append({'kind': 'transition_committed', 'id': transition_id,
                            'revision_sha256': _digest(revision) if revision else None})
        self.recent_steps.append({'step': actor_attempt + 1, 'analysis': str(thought or ''),
            'commands': [str(action) for action in action_batch],
            'observation': str(observation)})
        self.recent_steps = self.recent_steps[-8:]
        self.delivered = None
        self.pending_advice = None
        if not done:
            step = actor_attempt + 1
            triggered, reason = self.trigger.should_trigger(step)
            if triggered:
                result = await self.memory.process(self._pma_observation(), step,
                    advisory_context=self._phase2_context())
                self.pending_advice = result.context_for_action
            self.events.append({'kind': 'pma_wake', 'step': step,
                                'triggered': triggered, 'reason': reason,
                                'phase2_status': self.memory.last_phase2_status if triggered else None})
        else:
            self.ended = True
        return self.pos.get_context()

    def finish(self, *, reason, observation=None):
        self.pending_advice = None
        self.delivered = None
        self.ended = True
        result = self.pos.finish(reason=reason, observation=observation)
        return {'status': result['status'], 'pos': result,
                'bank': self.memory.memory.to_dict(), 'events': deepcopy(self.events)}

    def get_result(self):
        return {'status': 'partial', 'pos': self.pos.get_result(),
                'bank': self.memory.memory.to_dict(),
                'events': deepcopy(self.events)}

    def decision_completed(self, *, turn, action_count):
        return self.pos.decision_completed(turn=turn, action_count=action_count)
