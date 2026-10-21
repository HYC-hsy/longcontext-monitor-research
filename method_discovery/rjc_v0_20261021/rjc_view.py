"""RJC-v0: receipt-justified closure layered on pos_pma_shared_view_v1.

This module imports the frozen shared-view classes and extends them. Nothing in
pos_pma_complement_v1_20261019, the PoS vendor or the PMA vendor is modified.
PoS belief/consistency/progress roles and both PMA phases run exactly as before;
RJC adds a mechanical failure ledger (I1/I2), a closure review appended to the
consistency audit input (I4), ledger tags on memory entries written while a
goal-relevant failure was open (I5), and a completion-review payload (I3) that a
later GA gate may consume. No model role is added.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys

_COMPLEMENT = Path(__file__).resolve().parents[1] / 'pos_pma_complement_v1_20261019'
if str(_COMPLEMENT) not in sys.path:
    sys.path.insert(0, str(_COMPLEMENT))
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from candidate import _digest, _json  # noqa: E402
from failure_ledger import FailureLedger  # noqa: E402
from shared_view import (SharedViewBeliefManager, SharedViewEpisode,  # noqa: E402
                         SharedViewSentinel, shared_panel)

METHOD = 'pos_pma_rjc_v0'


def _gap_targets(context):
    targets = []
    for gap in [*context.get('epistemic_gaps', []), *context.get('achievement_gaps', [])]:
        target = gap.get('target') if isinstance(gap, dict) else None
        if isinstance(target, str) and target not in targets:
            targets.append(target)
    return targets


class RJCSentinel(SharedViewSentinel):
    """Shared-view audit plus a mechanical closure review on the consistency lane."""

    ledger = None
    closure_review = None

    def audit_candidate(self, **kwargs):
        self.closure_review = None
        if self.ledger is not None:
            before = kwargs.get('belief_before') or {}
            candidate = kwargs.get('candidate_belief') or {}
            after = set(_gap_targets(candidate))
            removed = [target for target in _gap_targets(before) if target not in after]
            self.closure_review = self.ledger.closure_review(removed,
                                                             step=kwargs.get('base_step'))
        try:
            return super().audit_candidate(**kwargs)
        finally:
            self.closure_review = None

    def _request_json(self, messages, caller, retries, **kwargs):
        if kwargs.get('lane') == 'consistency' and self.closure_review:
            body = _json(self.closure_review)
            messages = [*messages, {'role': 'system', 'content':
                'Receipt-justified closure review (mechanical ledger; not a tool '
                'result, not a verdict):\n' + body}]
            self.logger.log('rjc_closure_review_input',
                step=kwargs.get('step'), audit_mode=kwargs.get('audit_mode'),
                removed_gaps=self.closure_review['removed_gaps'],
                open_failure_ids=[item['failure_id'] for item in
                                  self.closure_review['items'] if item['status'] == 'open'],
                review_sha256=_digest(body), field_path='messages[-1].content')
        return super()._request_json(messages, caller, retries, **kwargs)


class RJCBeliefManager(SharedViewBeliefManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        prior = self.sentinel
        if prior is not None:
            self.sentinel = RJCSentinel(prior.config, prior.call_model, prior.logger,
                                        call_progress_model=prior.call_progress_model)
            self.sentinel.shared_sources = ()
            self.sentinel.strict_audit_contract = True
            self.sentinel.shared_audit_semantics_v1 = True
            self.sentinel.shared_evidence_id_v1 = True
            self.sentinel.ledger = None


def rjc_panel(context, *, advice=None, ledger=None):
    base = shared_panel(context, advice=advice)
    section = ledger.panel_section() if ledger is not None else ''
    if not section:
        return {**base, 'ledger_section_sha256': None}
    panel = base['panel'] + '\n\n' + section
    return {**base, 'panel': panel, 'panel_sha256': _digest(panel),
            'ledger_section_sha256': _digest(section)}


class RJCEpisode(SharedViewEpisode):
    """Shared-view episode with a receipt ledger; PMA and PoS calls unchanged."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ledger = None
        self.memory_failure_tags = {}

    async def reset(self, *, task, observation, actions):
        self.ledger = FailureLedger(task)
        if self.manager.sentinel is not None:
            self.manager.sentinel.ledger = self.ledger
        return await super().reset(task=task, observation=observation, actions=actions)

    async def update(self, *, actor_attempt, transition_id, thought, action_batch,
                     observation, source_events=(), done=False):
        if self.ledger is None:
            raise RuntimeError('RJC ledger requires reset before update')
        summary = self.ledger.ingest(turn=actor_attempt, transition_id=transition_id,
                                     action_batch=action_batch, source_events=source_events)
        self.events.append({'kind': 'rjc_ledger_ingested', **summary,
                            'open_goal_relevant': self.ledger.tag_for_now()})
        return await super().update(actor_attempt=actor_attempt, transition_id=transition_id,
            thought=thought, action_batch=action_batch, observation=observation,
            source_events=source_events, done=done)

    def _freeze(self):
        # I5: entries written in this wake get the ledger state at write time.
        open_ids = self.ledger.tag_for_now() if self.ledger is not None else []
        for operation in self.memory.last_phase1_operations:
            if operation.success and operation.action in {'save_knowledge', 'save_procedural'}:
                self.memory_failure_tags[operation.memory_id] = {
                    'open_goal_relevant_failures_at_write': list(open_ids),
                    'ledger_version': self.ledger.version if self.ledger else 0}
        super()._freeze()

    def _bind_selection(self):
        super()._bind_selection()
        tags = {entry['id']: deepcopy(self.memory_failure_tags[entry['id']])
                for entry in self.frozen_selection['entries']
                if entry['id'] in self.memory_failure_tags}
        note = {'tags': tags, 'meaning': 'mechanical ledger state when the entry was '
                'written; not a judgement about the entry content'}
        self.manager.shared_history['memory_failure_tags'] = note
        sentinel = self.manager.sentinel
        if sentinel is not None and sentinel.shared_selection is not None:
            sentinel.shared_selection['memory_failure_tags'] = deepcopy(note)
        self.events.append({'kind': 'rjc_memory_tags_bound',
                            'tagged_entry_ids': sorted(tags)})

    def decision_panel(self, *, observation):
        if not self.started or self.ended:
            raise RuntimeError('rjc episode not active')
        panel = rjc_panel(self._context(), advice=self.pending_advice, ledger=self.ledger)
        self.events.append({'kind': 'panel_prepared',
            'panel_sha256': panel['panel_sha256'],
            'advice_sha256': panel['advice_sha256'],
            'ledger_section_sha256': panel['ledger_section_sha256']})
        return panel

    def completion_review(self, *, turn):
        """I3 payload for a GA completion gate; mechanical, no model call."""
        if not self.started:
            raise RuntimeError('rjc episode not initialized')
        context = self._context()
        gaps = [{'gap_type': 'epistemic', **gap} for gap in context.get('epistemic_gaps', [])]
        gaps += [{'gap_type': 'achievement', **gap} for gap in context.get('achievement_gaps', [])]
        review = self.ledger.completion_review(
            open_gaps=gaps, stale=context.get('latest_update_outcome') == 'unusable',
            state_version=context.get('accepted_revision'))
        review['turn'] = turn
        self.events.append({'kind': 'rjc_completion_review', 'turn': turn,
                            'fires': review['fires'], 'open_gap_count': len(gaps),
                            'open_failure_ids': [item['failure_id'] for item in
                                                 review['items'] if item['status'] == 'open'],
                            'review_sha256': _digest(_json(review))})
        return review

    def _rjc_result_fields(self):
        return {'method': METHOD,
                'rjc_ledger': self.ledger.snapshot() if self.ledger is not None else None,
                'memory_failure_tags': deepcopy(self.memory_failure_tags)}

    def get_result(self):
        return {**super().get_result(), **self._rjc_result_fields()}

    def finish(self, *, reason, observation=None):
        result = super().finish(reason=reason, observation=observation)
        return {**result, **self._rjc_result_fields()}
