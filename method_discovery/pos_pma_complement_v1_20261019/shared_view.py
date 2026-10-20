"""Default-off shared historical selection and single GA view.

The released PMA bank and PoS manager remain unchanged. This module is an
explicitly different candidate input/scheduling adapter, not a baseline fix.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json

from candidate import (ComplementBeliefManager, ComplementEpisode,
                       CandidateSentinel, _digest, _health_progress_signal,
                       _json, _required_state)
from citation_fix import CitationFixedSentinel, _result_fields
from prompts.react_prompt import _frontier_relevant_world


METHOD = 'pos_pma_shared_view_v1'


def _visible_tool_sources(source):
    if not isinstance(source, dict) or not isinstance(source.get('result'), (str, dict, list)):
        return ()
    if source.get('origin') in {'task', 'initial_task', 'model', 'advice'}:
        return ()
    return tuple(_result_fields(source['result'], 'result'))


class SharedViewSentinel(CandidateSentinel):
    """Project supplemental history through the original per-step audit cap."""

    def _request_json(self, messages, caller, retries, **kwargs):
        if kwargs.get('lane') == 'consistency' and getattr(self, 'shared_selection', None):
            selection = self.shared_selection
            history = {'selection': selection,
                'meaning': 'selected PMA memory is fallible historical interpretation; '
                           'it is not a tool receipt or citable evidence'}
            body = _json(history)
            messages = [*messages, {'role': 'system', 'content':
                'Frozen selected PMA history for this audit (not a tool result):\n' + body}]
            self.logger.log('shared_audit_history_input',
                step=kwargs.get('step'), audit_mode=kwargs.get('audit_mode'),
                entry_ids=[item['id'] for item in selection['entries']],
                selection_sha256=_digest(selection['rendered_text']),
                request_context_sha256=_digest(body),
                field_path='messages[-1].content')
        return super()._request_json(messages, caller, retries, **kwargs)

    def _compact_trajectory(self, trajectory):
        # The old complement's supplemental_sources path would grant a second
        # independent projection allowance. Begin with the native bounded view.
        compact = CitationFixedSentinel._compact_trajectory(self, trajectory)
        task_only_hash = getattr(self, 'task_only_initial_sha256', None)
        for original, shown in zip(trajectory, compact):
            if (original.get('step') == -1 and task_only_hash and
                    _digest(str(original.get('observation', ''))) == task_only_hash):
                shown['citable_sources'] = []
                shown['source_origin'] = 'original_task_not_tool_result'
        by_step = {row['step']: row for row in compact}
        seen = set()
        for original, row in zip(trajectory, compact):
            try:
                envelope = json.loads(original.get('observation', ''))
            except (TypeError, ValueError):
                row['citable_sources'] = []
                row.setdefault('source_origin', 'unidentified_plain_observation')
                continue
            receipts = envelope.get('tool_results') if isinstance(envelope, dict) else None
            if not isinstance(receipts, list):
                row['citable_sources'] = []
                row.setdefault('source_origin', 'not_a_tool_result_envelope')
                continue
            for field in row.get('citable_sources', ()):
                path = field.get('source_path', '')
                if not path.startswith('tool_results['):
                    continue
                try:
                    index = int(path.split('[', 1)[1].split(']', 1)[0])
                    receipt = receipts[index]
                except (IndexError, ValueError, TypeError):
                    continue
                if not isinstance(receipt, dict):
                    continue
                event_id = receipt.get('tool_use_id') or receipt.get('event_id')
                if event_id is None:
                    continue
                field_path = path.split(']', 1)[1].lstrip('.')
                root_key = field_path.split('.', 1)[0]
                original_fields = dict(_result_fields(
                    receipt.get(root_key), root_key))
                original_value = original_fields.get(field_path)
                field['event_id'] = str(event_id)
                field['source_path'] = str(event_id) + ':' + field_path
                if isinstance(original_value, str):
                    field['offset'] = (len(original_value) - len(field['text'])
                        if field.get('truncated') and field.get('segment') == 1 else 0)
                    if field.get('truncated') and field.get('segment') == 0:
                        row.setdefault('shared_omitted', []).append({
                            'event_id': str(event_id), 'field_path': field_path,
                            'offset': len(field['text']),
                            'length': len(original_value) - 2 * len(field['text']),
                            'reason': 'native_audit_projection'})
                seen.add((str(event_id), field_path))
        for source in getattr(self, 'shared_sources', ()):
            step = source.get('pos_step')
            if not isinstance(step, int) or step < 0:
                continue  # task-only initialization is not a tool observation
            fields = _visible_tool_sources(source.get('raw'))
            if not fields:
                continue
            row = by_step.get(step)
            if row is None:
                row = {'step': step, 'action': None, 'observation': '',
                       'citable_sources': []}
                compact.append(row)
                by_step[step] = row
            used = sum(len(item['text']) for item in row.get('citable_sources', ()))
            for path, value in fields:
                identity = (source['event_id'], path)
                if identity in seen:
                    continue
                seen.add(identity)
                remaining = self.audit_observation_max_chars - used
                if remaining <= 0:
                    row.setdefault('shared_omitted', []).append({
                        'event_id': source['event_id'], 'field_path': path,
                        'offset': 0, 'length': len(value), 'reason': 'audit_cap'})
                    continue
                if len(value) > remaining:
                    head = (remaining + 1) // 2
                    tail = remaining - head
                    pieces = ((0, value[:head]),
                              (len(value) - tail, value[-tail:] if tail else ''))
                    clipped = True
                else:
                    pieces = ((0, value),)
                    clipped = False
                for offset, text in pieces:
                    if not text:
                        continue
                    record = {'source_path': source['event_id'] + ':' + path,
                              'offset': offset, 'text': text,
                              'truncated': clipped}
                    row['citable_sources'].append(record)
                    row.setdefault('shared_history', []).append({
                        'event_id': source['event_id'], 'sha256': source['sha256'],
                        'actor_transition_id': source.get('actor_transition_id'),
                        'pos_step': step, 'segment': record})
                    used += len(text)
                if clipped:
                    row.setdefault('shared_omitted', []).append({
                        'event_id': source['event_id'], 'field_path': path,
                        'offset': head, 'length': len(value) - remaining,
                        'reason': 'audit_cap'})
        self.logger.log('shared_audit_source_projection',
            rows=[{'step': row['step'], 'sources': [{
                'event_id': item.get('event_id'),
                'field_path': item.get('source_path'),
                'offset': item.get('offset', 0),
                'sha256': _digest(item['text'])} for item in row.get('citable_sources', ())],
                'omitted': row.get('shared_omitted', [])} for row in compact])
        return compact


class SharedViewBeliefManager(ComplementBeliefManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        prior = self.sentinel
        if prior is not None:
            self.sentinel = SharedViewSentinel(prior.config, prior.call_model,
                prior.logger, call_progress_model=prior.call_progress_model)
            self.sentinel.shared_sources = ()
        self.shared_history = None

    def _request_candidate(self, messages, *, base, operation, step):
        if self.shared_history is not None and operation in {
                'initialize', 'update', 'sentinel_repair'}:
            messages = [dict(item) for item in messages]
            messages.append({'role': 'system', 'content':
                'Selected PMA history and original source identities are fallible '
                'context, not a new tool result or a Sentinel finding:\n' +
                _json(self.shared_history)})
        # Do not call the former candidate's revision-context injection here.
        from citation_fix import CitationFixedBeliefManager
        return CitationFixedBeliefManager._request_candidate(
            self, messages, base=base, operation=operation, step=step)


def shared_panel(context, *, advice=None):
    state = _required_state(context, include_recovery=True)
    world = _frontier_relevant_world(context.get('world', {}),
                                    context.get('frontier_gap'))
    panel = ('Auxiliary model-generated view; not a new user requirement, tool '
             'receipt or completion approval. Original Task and actual GA '
             'observations remain authoritative.\n' + _json({
                 'state': state, 'frontier_relevant_world': world,
                 'recovery': context.get('recovery')}))
    if advice:
        panel += '\n\nOptional PMA advice (fallible):\n' + advice
    return {'panel': panel, 'panel_sha256': _digest(panel),
            'included_advice': advice or None,
            'advice_sha256': _digest(advice) if advice else None,
            'budget_suppressed': False, 'omitted': []}


class SharedViewEpisode(ComplementEpisode):
    """One frozen bank choice per wake, before a single PoS state transition."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_transitions = set()
        self.frozen_selection = None
        self.initialization_stage = 'not_attempted'
        self.phase1_status = 'not_attempted'
        self.phase2_status = 'not_attempted'
        self.pending_source_pack = []
        self.current_attempt = {'kind': 'not_attempted'}

    def _selection_sources(self):
        selected = []
        seen = set()
        selection = self.frozen_selection or {}
        for entry in selection.get('entries', ()):
            mapping = selection.get('source_mappings', {}).get(entry['id'])
            if not mapping:
                selected.append({'memory_id': entry['id'], 'source': 'unknown'})
                continue
            for event_id in mapping['input_sources']:
                if event_id in seen:
                    continue
                seen.add(event_id)
                source = self.source_registry.get(event_id)
                if source is None:
                    selected.append({'memory_id': entry['id'], 'event_id': event_id,
                                     'source': 'unknown'})
                else:
                    projected = deepcopy(source)
                    if projected.get('origin') == 'tool_result':
                        # Host next_prompt/arguments/metadata are not a tool
                        # return, even when nested beside one in the receipt.
                        projected['raw'] = {'result': deepcopy(
                            source['raw'].get('result'))}
                    selected.append(projected)
        return selected

    def _bind_selection(self):
        sources = self._selection_sources()
        self.manager.shared_history = {'selection': deepcopy(self.frozen_selection),
                                       'sources': sources,
                                       'provenance_meaning': 'visible_at_creation_only'}
        if self.manager.sentinel is not None:
            self.manager.sentinel.shared_sources = tuple(
                source for source in sources if source.get('origin') == 'tool_result')
            self.manager.sentinel.shared_selection = deepcopy(self.frozen_selection)
        self.events.append({'kind': 'shared_selection_bound',
            'entry_ids': [entry['id'] for entry in self.frozen_selection['entries']],
            'bank_version': self.frozen_selection['bank_version'],
            'source_ids': [source.get('event_id') for source in sources],
            'render_sha256': _digest(self.frozen_selection['rendered_text'])})

    def _clear_selection(self):
        self.manager.shared_history = None
        if self.manager.sentinel is not None:
            self.manager.sentinel.shared_sources = ()
            self.manager.sentinel.shared_selection = None

    def _freeze(self):
        self.frozen_selection = self.memory.freeze_selection(self._phase1_observation())
        self._bind_selection()

    def _phase1_observation(self):
        observation = self._pma_observation()
        if self.started:
            prior = _required_state(self._context(), include_recovery=True)
            observation += ('\n\n[Previously adopted PoS interpretation — '
                'not a tool observation]\n' + _json(prior))
        return observation

    def _phase2_context(self):
        context = self._context()
        signal, health, progress = _health_progress_signal(self, context)
        selected_sources = self._selection_sources()
        explanations = {'health': {key: health.get(key) for key in
            ('persistent_epistemic_gaps', 'persistent_achievement_gaps')},
            'progress': ({key: progress.get(key) for key in
                ('reason', 'affected_record_ids')} if progress else None)}
        previous = self.advice_history[-1] if self.advice_history else None
        return _json({'original_task': self.original_task,
            'adopted_state': _required_state(context, include_recovery=True),
            'health_progress': signal, 'explanations': explanations,
            'last_delivered_advice_and_consequence': previous,
            'selected_memory_input_sources': selected_sources,
            'selected_source_count': len(selected_sources),
            'selected_source_utf8_bytes': len(_json(selected_sources).encode('utf-8')),
            'frozen_bank_selection_sha256': _digest(
                self.frozen_selection['rendered_text']) if self.frozen_selection else None})

    def decision_panel(self, *, observation):
        if not self.started or self.ended:
            raise RuntimeError('shared-view episode not active')
        panel = shared_panel(self._context(), advice=self.pending_advice)
        self.events.append({'kind': 'panel_prepared',
            'panel_sha256': panel['panel_sha256'],
            'advice_sha256': panel['advice_sha256']})
        return panel

    def _safe_pos_result(self):
        try:
            return self.pos.get_result()
        except BaseException as error:
            return {'status': 'unavailable', 'stage': self.initialization_stage,
                    'error_type': type(error).__name__}

    def get_result(self):
        return {'status': 'partial', 'pos': self._safe_pos_result(),
            'bank': self.memory.memory.to_dict(), 'events': deepcopy(self.events),
            'advice_history': deepcopy(self.advice_history),
            'source_registry': deepcopy(self.source_registry),
            'entry_sources': deepcopy(self.memory.entry_sources),
            'rendered_bank_entries': deepcopy(self.memory.rendered_entry_ids),
            'last_phase1_operations': [asdict(item) for item in
                self.memory.last_phase1_operations],
            'phase1_status': self.phase1_status, 'phase2_status': self.phase2_status,
            'initialization_stage': self.initialization_stage,
            'current_attempt': deepcopy(self.current_attempt),
            'frozen_selection': deepcopy(self.frozen_selection)}

    async def reset(self, *, task, observation, actions):
        if self.started:
            raise RuntimeError('shared-view episode already initialized')
        if (self.memory.memory.status or self.memory.memory.knowledge or
                self.memory.memory.procedural):
            raise ValueError('shared-view requires a fresh PMA bank')
        self.original_task = task
        self.current_attempt = {'kind': 'initialization', 'stage': 'phase1',
                                'reviewed': False}
        self.phase1_status = 'not_attempted'
        self.phase2_status = 'not_attempted'
        self.frozen_selection = None
        self.memory.last_phase1_operations = []
        self.memory.frozen_selection = None
        self.source_registry['original-task'] = {
            'event_id': 'original-task', 'origin': 'original_task',
            'raw': {'task': task}, 'sha256': _digest(task), 'order': -1,
            'pos_step': None, 'actor_transition_id': None}
        self.trigger.reset()
        triggered, reason = self.trigger.should_trigger(1)
        if not triggered:
            self.phase1_status = 'not_triggered'
            self.phase2_status = 'not_triggered'
        self.events.append({'kind': 'initial_trigger', 'step': 1,
                            'triggered': triggered, 'reason': reason,
                            'initial_observation_origin': 'task_only'})
        if triggered:
            self.phase1_status = 'started'
            try:
                await self.memory.phase1(self._phase1_observation(), 1,
                                         input_sources=self._input_sources())
                self.phase1_status = 'completed'
            except BaseException:
                self.phase1_status = 'failed'
                self.current_attempt['stage'] = 'phase1_failed'
                raise
        self._freeze()
        self.initialization_stage = 'pos_initializing'
        self.current_attempt['stage'] = 'pos_initializing'
        try:
            if self.manager.sentinel is not None:
                self.manager.sentinel.task_only_initial_sha256 = (
                    _digest(observation) if observation == task else None)
            # The host supplies initial_content as both parameters. It remains
            # a task-only row and never becomes a tool-result citation.
            self.pos.reset(task=task, observation=observation, actions=actions)
            if (self.manager.sentinel is not None and
                    self.manager.sentinel.last_format_rejection):
                raise RuntimeError('shared-view initialization audit format rejected')
            self.started = True
            self.latest_update_outcome = self.manager.last_validation_outcome
            self.initialization_stage = 'pos_initialized'
            self.current_attempt['stage'] = 'pos_initialized'
            self.current_attempt['reviewed'] = True
        finally:
            self._clear_selection()
        if triggered:
            self.phase2_status = 'started'
            try:
                result = await self.memory.phase2(self._pma_observation(), 1,
                    advisory_context=self._phase2_context())
                self.pending_advice = result['reminder']
                self.pending_source_pack = (self._selection_sources()
                                            if self.pending_advice else [])
                self.phase2_status = result['status']
            except BaseException:
                self.phase2_status = 'failed'
                self.current_attempt['stage'] = 'phase2_failed'
                raise
        self.current_attempt['stage'] = 'completed'
        self.events.append({'kind': 'reset', 'triggered': triggered,
            'phase1_status': self.phase1_status,
            'phase2_status': self.phase2_status,
            'initialization_stage': self.initialization_stage})
        return self.decision_panel(observation=observation)

    async def update(self, *, actor_attempt, transition_id, thought,
                     action_batch, observation, source_events=(), done=False):
        if not self.started or self.ended:
            raise RuntimeError('shared-view episode not active')
        if not isinstance(transition_id, str) or not transition_id:
            raise ValueError('stable transition identity required')
        if transition_id in self.processed_transitions:
            raise ValueError('duplicate shared-view transition')
        if not action_batch:
            raise ValueError('shared-view update requires a real action batch')
        # A skipped PMA wake still needs a fresh selection from the unchanged
        # bank, rather than the prior wake's frozen render.
        self.current_attempt = {'kind': 'transition', 'transition_id': transition_id,
                                'stage': 'result_recorded', 'reviewed': False}
        self.phase1_status = 'not_attempted'
        self.phase2_status = 'not_attempted'
        self.frozen_selection = None
        self.memory.last_phase1_operations = []
        self.memory.frozen_selection = None
        self.processed_transitions.add(transition_id)
        for index, item in enumerate(source_events):
            if not isinstance(item, dict):
                continue
            event_id = str(item.get('tool_use_id') or item.get('event_id') or
                           f'{transition_id}:source:{index}')
            raw = _json(item)
            if event_id in self.source_registry:
                if self.source_registry[event_id]['sha256'] != _digest(raw):
                    raise ValueError('source identity/hash conflict')
                continue
            self.source_registry[event_id] = {
                'event_id': event_id, 'origin': 'tool_result',
                'raw': deepcopy(item), 'sha256': _digest(raw),
                'order': len(self.source_registry),
                'actor_transition_id': transition_id,
                'pos_step': self.pos.step}
        self.recent_steps.append({'step': actor_attempt + 1,
            'analysis': str(thought or ''),
            'commands': [str(action) for action in action_batch],
            'observation': str(observation),
            'source_ids': [str(item.get('tool_use_id') or item.get('event_id'))
                for item in source_events if isinstance(item, dict)]})
        self.recent_steps = self.recent_steps[-self.recent_window:]
        self.events.append({'kind': 'transition_result_recorded',
            'transition_id': transition_id, 'source_ids':
            deepcopy(self.recent_steps[-1]['source_ids']), 'reviewed': False})
        triggered = False
        reason = 'terminal_batch'
        step = actor_attempt + 1
        if not done:
            triggered, reason = self.trigger.should_trigger(step)
            if triggered:
                self.phase1_status = 'started'
                try:
                    await self.memory.phase1(self._phase1_observation(), step,
                        input_sources=self._input_sources())
                    self.phase1_status = 'completed'
                except BaseException:
                    self.phase1_status = 'failed'
                    self.current_attempt['stage'] = 'phase1_failed'
                    self.events.append({'kind': 'phase1_failed',
                        'transition_id': transition_id,
                        'pos_update': 'not_attempted',
                        'phase2': 'not_attempted'})
                    raise
            else:
                self.phase1_status = 'not_triggered'
        else:
            self.phase1_status = 'skipped_terminal'
        self._freeze()
        self.current_attempt['stage'] = 'pos_updating'
        if self.delivered:
            self.manager.shared_history['previous_delivered_advice'] = {
                'advice': self.delivered['advice'],
                'advice_sha256': self.delivered['advice_sha256'],
                'delivery_event_id': self.delivered['delivery_event_id'],
                'completed_transition_id': transition_id,
                'frozen_sources': deepcopy(self.delivered.get('source_pack', []))}
            if self.manager.sentinel is not None:
                combined = list(self.manager.sentinel.shared_sources)
                identities = {(item.get('event_id'), item.get('sha256'))
                              for item in combined}
                for item in self.delivered.get('source_pack', []):
                    identity = (item.get('event_id'), item.get('sha256'))
                    if (item.get('origin') == 'tool_result' and
                            identity not in identities):
                        combined.append(deepcopy(item))
                        identities.add(identity)
                self.manager.sentinel.shared_sources = tuple(combined)
        try:
            self.pos.update(thought=thought, action_batch=action_batch,
                            observation=observation, done=done)
        finally:
            self._clear_selection()
        outcome = self.manager.last_validation_outcome
        self.current_attempt['stage'] = 'pos_processed'
        self.current_attempt['reviewed'] = True
        if outcome == 'accepted':
            self.accepted_revision += 1
        self.latest_update_outcome = outcome
        self.latest_actor_transition = transition_id
        self.events.append({'kind': 'transition_processed', 'id': transition_id,
            'update_outcome': outcome,
            'accepted_revision': self.accepted_revision,
            'pma_triggered': triggered, 'trigger_reason': reason,
            'selected_bank_sha256': _digest(self.frozen_selection['rendered_text'])})
        if self.delivered:
            self.advice_history[-1]['reviewed_transition'] = transition_id
            self.advice_history[-1]['review_outcome'] = outcome
            self.advice_history[-1]['actual_results'] = deepcopy(list(source_events))
        self.delivered = None
        self.pending_advice = None
        if done:
            self.ended = True
            self.phase2_status = 'skipped_terminal'
        elif triggered:
            self.phase2_status = 'started'
            try:
                result = await self.memory.phase2(self._pma_observation(), step,
                    advisory_context=self._phase2_context())
                self.pending_advice = result['reminder']
                self.pending_source_pack = (self._selection_sources()
                                            if self.pending_advice else [])
                self.phase2_status = result['status']
            except BaseException:
                self.phase2_status = 'failed'
                self.current_attempt['stage'] = 'phase2_failed'
                raise
        else:
            self.phase2_status = 'not_triggered'
        self.current_attempt['stage'] = 'completed'
        return self._context()

    def finish(self, *, reason, observation=None):
        self.pending_advice = None
        self.delivered = None
        self.ended = True
        result = self.pos.finish(reason=reason, observation=observation)
        return {'status': result['status'], 'pos': result,
                'bank': self.memory.memory.to_dict(),
                'events': deepcopy(self.events),
                'advice_history': deepcopy(self.advice_history),
                'source_registry': deepcopy(self.source_registry),
                'entry_sources': deepcopy(self.memory.entry_sources),
                'rendered_bank_entries': deepcopy(self.memory.rendered_entry_ids),
                'last_phase1_operations': [asdict(item) for item in
                    self.memory.last_phase1_operations],
                'phase1_status': self.phase1_status,
                'phase2_status': self.phase2_status,
                'current_attempt': deepcopy(self.current_attempt)}
