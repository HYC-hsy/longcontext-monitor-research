"""Opt-in branch adapter: phase-2 selects pinned, committed verbatim text."""

import hashlib
import json
import uuid

from citation_gate_agent import CitationGateMemoryAgent
from pma_evidence_review.verbatim_selection_prototype_20261031.contract import (
    MemoryRef, freeze_snapshot, parse_and_render, delivery_json,
)


SELECTION_SYSTEM = """You are choosing whether to remind the task agent using only
the visible task and committed memory candidates in the current prompt. Internal
status helps your judgment but is not selectable. Recently visible information
may still be worth selecting when the task agent's behavior contradicts it.
Do not write a reminder, summary, new fact, conclusion, or revised memory.
Return exactly one JSON object with cycle, task_version, decision, references.
decision is intervene or no_intervention. intervene requires one or more ordered
references; no_intervention requires an empty list. A task reference has only
kind=task and version. A memory reference has only kind=memory, id, revision.
Select only identities shown in the current candidate list. No extra fields.
"""

_OLD_TASK = """## Your Task
Review the memory bank and the agent's recent trajectory. Decide:
- Is the agent missing or forgetting something important from the memory bank?
- Is the agent heading toward a pattern that matches a recorded failure?

If yes, write a <context_for_action> note with the relevant context.
If no, write <no_intervention/>.
"""


def _hash(text):
    return hashlib.sha256(text.encode('utf-8', errors='surrogatepass')).hexdigest()


class VerbatimSelectionCitationGateAgent(CitationGateMemoryAgent):
    """Keep phase-1 gate untouched; change only phase-2 output and presentation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selection_snapshot = None
        self._active_selection_cycle = None
        self._phase2_visible = None
        self.last_selection_report = {}

    def _format_memory_list(self, entries):
        if self._phase2_visible is not None:
            for entry in entries:
                self._phase2_visible.setdefault(entry.id, entry)
        return super()._format_memory_list(entries)

    def _build_phase2_prompt(self, observation, step_count):
        self._phase2_visible = {}
        self._selection_snapshot = None
        cycle = 'selection_' + uuid.uuid4().hex
        self._active_selection_cycle = cycle
        self.last_selection_report = {'cycle': cycle, 'status': 'building',
                                      'excluded_legacy_ids': []}
        try:
            prompt = super()._build_phase2_prompt(observation, step_count)
            original_instruction = prompt.rfind(_OLD_TASK)
            if original_instruction < 0:
                raise RuntimeError('phase2_prompt_shape_changed')
            prompt = (prompt[:original_instruction] +
                      prompt[original_instruction + len(_OLD_TASK):])
            records = []
            for entry in self._phase2_visible.values():
                revision_id = self.memory.active_revisions.get(entry.id)
                revision = self.memory.revisions.get(revision_id) if revision_id else None
                if revision is None:
                    self.last_selection_report['excluded_legacy_ids'].append(entry.id)
                    continue
                if (revision.memory_id != entry.id or
                        revision.category not in {'knowledge', 'procedural', 'gap'} or
                        revision.content_sha256 != _hash(entry.content) or
                        self.memory.blobs.get(revision.content_sha256) != entry.content):
                    raise ValueError('committed_revision_content_mismatch')
                records.append({'id': entry.id, 'revision': revision_id,
                                'category': revision.category, 'text': entry.content})
            version = 'task_sha256_' + _hash(self.task)
            snapshot = freeze_snapshot(cycle, version, self.task,
                                       self.memory.status or '', records)
            self._selection_snapshot = snapshot
            candidates = [{'kind': 'task', 'version': version, 'text': self.task}]
            candidates += [{'kind': 'memory', 'id': row.id, 'revision': row.revision,
                            'category': row.category, 'text': row.text} for row in snapshot.items]
            self.last_selection_report.update(status='request_built', task_version=version,
                task_sha256=_hash(self.task),
                candidates=[{'id': row.id, 'revision': row.revision,
                             'category': row.category, 'content_sha256': _hash(row.text)}
                            for row in snapshot.items])
            return prompt + '\n## Selectable frozen candidates\n' + json.dumps(
                {'cycle': cycle, 'task_version': version, 'candidates': candidates},
                ensure_ascii=True, sort_keys=True) + '\n\n## Required output\n' + json.dumps(
                {'cycle': cycle, 'task_version': version, 'decision': 'intervene',
                 'references': [{'kind': 'task', 'version': version}]},
                ensure_ascii=True, sort_keys=True) + '\n'
        except Exception as exc:
            self.last_selection_report.update(status='selection_error', error=type(exc).__name__)
            self.last_gap_report['selection_error'] = self.last_selection_report.copy()
            raise
        finally:
            self._phase2_visible = None

    async def _call_llm_phase2(self, user_prompt):
        self._sent_phase2 = user_prompt
        self.last_gap_report['actual_phase2_prompt'] = user_prompt
        self.transport_phase = 'selection'
        try:
            return await self.llm.call(prompt=user_prompt, system=SELECTION_SYSTEM)
        except Exception as exc:
            self.last_selection_report.update(status='selection_error', error=type(exc).__name__)
            self.last_gap_report['selection_error'] = self.last_selection_report.copy()
            self.last_gap_report['transport_errors'].append(
                {'phase': 'selection', 'type': type(exc).__name__})
            raise

    def _parse_phase2_response(self, raw):
        snapshot = self._selection_snapshot
        if snapshot is None:
            self.last_selection_report.update(status='selection_error', error='missing_snapshot')
            self.last_gap_report['selection_error'] = self.last_selection_report.copy()
            return None
        outcome = parse_and_render(raw, snapshot,
            active_cycle=self._active_selection_cycle,
            active_task_version='task_sha256_' + _hash(self.task))
        if outcome.kind == 'error':
            self.last_selection_report.update(status='selection_error', error=outcome.error)
            self.last_gap_report['selection_error'] = self.last_selection_report.copy()
            return None
        self.last_selection_report.update(status=outcome.kind,
            selected=[({'kind': 'task', 'version': block.reference.version}
                       if not isinstance(block.reference, MemoryRef) else
                       {'kind': 'memory', 'id': block.reference.id,
                        'revision': block.reference.revision}) for block in outcome.blocks])
        self.last_gap_report['selection'] = self.last_selection_report.copy()
        if outcome.kind == 'no_intervention':
            return None
        return delivery_json(outcome)

    def pending_refs_valid(self):
        """Do not substitute a later revision before the pending Task delivery."""
        snapshot = self._selection_snapshot
        if (snapshot is None or self.last_selection_report.get('status') != 'intervention'
                or snapshot.cycle != self._active_selection_cycle
                or snapshot.task_version != 'task_sha256_' + _hash(self.task)):
            self.last_gap_report['delivery_error'] = 'stale_selection_snapshot'
            return False
        for selected in self.last_selection_report.get('selected', ()):
            if selected['kind'] != 'memory':
                continue
            if self.memory.active_revisions.get(selected['id']) != selected['revision']:
                self._active_selection_cycle = None
                self.last_gap_report['delivery_error'] = 'selection_revision_revoked'
                return False
        return True
