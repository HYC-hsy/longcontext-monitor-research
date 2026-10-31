"""Phase-2 tag/alias selection over pinned committed text; phase 1 is unchanged."""

import hashlib
import json
import uuid

from citation_gate_agent import CitationGateMemoryAgent
from tag_selection_contract import (Item, Snapshot, PROTOCOL_VERSION,
    SELECTION_SYSTEM, dispatch, delivery_json, diagnostic)


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
    """Existing gated reviewer and bank, with a strict phase-2 tag protocol."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selection_snapshot = None
        self._active_selection_cycle = None
        self._phase2_visible = None
        self._completion_call_id = None
        self.last_selection_report = {}

    def _format_memory_list(self, entries):
        if self._phase2_visible is not None:
            for entry in entries:
                self._phase2_visible.setdefault(entry.id, entry)
        return super()._format_memory_list(entries)

    def _active_records(self):
        records = {}
        for category in ('knowledge', 'procedural', 'gap'):
            entries = self.gaps.entries if category == 'gap' else getattr(self.memory, category)
            for entry in entries:
                revision_id = self.memory.active_revisions.get(entry.id)
                revision = self.memory.revisions.get(revision_id) if revision_id else None
                if revision is None:
                    continue
                if (revision.memory_id != entry.id or revision.category != category or
                        revision.content_sha256 != _hash(entry.content) or
                        self.memory.blobs.get(revision.content_sha256) != entry.content):
                    raise ValueError('committed_revision_content_mismatch')
                records[entry.id] = Item(entry.id, revision_id, category, entry.content)
        return records

    def _build_phase2_prompt(self, observation, step_count):
        self._phase2_visible = {}
        self._selection_snapshot = None
        self._completion_call_id = None
        cycle = 'selection_' + uuid.uuid4().hex
        self._active_selection_cycle = cycle
        self.last_selection_report = {'cycle': cycle, 'protocol': PROTOCOL_VERSION,
                                      'status': 'building', 'excluded_legacy_ids': []}
        try:
            prompt = super()._build_phase2_prompt(observation, step_count)
            index = prompt.rfind(_OLD_TASK)
            if index < 0:
                raise RuntimeError('phase2_prompt_shape_changed')
            prompt = prompt[:index] + prompt[index + len(_OLD_TASK):]
            live = self._active_records()
            items = []
            for entry in self._phase2_visible.values():
                row = live.get(entry.id)
                if row is None:
                    self.last_selection_report['excluded_legacy_ids'].append(entry.id)
                    continue
                items.append(row)
            version = 'task_sha256_' + _hash(self.task)
            snapshot = Snapshot(uuid.uuid4().hex, cycle, version, self.task, tuple(items))
            self._selection_snapshot = snapshot
            self.last_selection_report.update(status='request_built',
                call_id=snapshot.call_id, task_version=version, task_sha256=_hash(self.task),
                candidates=[{'alias': f'M{i}', 'id': row.id, 'revision': row.revision,
                             'category': row.category, 'content_sha256': _hash(row.content)}
                            for i, row in enumerate(items, 1)])
            catalogue = [{'alias': 'TASK', 'content': self.task}]
            catalogue += [{'alias': f'M{i}', 'category': row.category, 'content': row.content}
                          for i, row in enumerate(items, 1)]
            return prompt + '\n## Selectable catalogue\n' + json.dumps(
                catalogue, ensure_ascii=True, sort_keys=True) + (
                '\n\nOnly TASK and the listed M aliases may be selected. The status and\n'
                'recent eight visible steps above are judgment context only.\n'
                'Return one bare <intervene>TASK,M1</intervene> or <no_intervention/>.\n')
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
        snapshot = self._selection_snapshot
        self._completion_call_id = snapshot.call_id if snapshot else None
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
        try:
            active = self._active_records()
            outcome = dispatch(raw, snapshot, completion_call_id=self._completion_call_id,
                active_cycle=self._active_selection_cycle,
                active_task_version='task_sha256_' + _hash(self.task), active_records=active)
        except Exception as exc:
            self.last_selection_report.update(status='selection_error', error=type(exc).__name__)
            self.last_gap_report['selection_error'] = self.last_selection_report.copy()
            return None
        self.last_selection_report.update(diagnostic(outcome))
        self.last_selection_report['status'] = ('selection_error' if outcome.kind == 'error'
                                                else outcome.kind)
        if outcome.kind == 'error':
            self.last_gap_report['selection_error'] = self.last_selection_report.copy()
            return None
        self.last_selection_report['selected'] = [
            {k: block[k] for k in ('alias', 'id', 'revision', 'category')}
            for block in outcome.blocks]
        self.last_gap_report['selection'] = self.last_selection_report.copy()
        return delivery_json(outcome)

    def pending_refs_valid(self):
        snapshot = self._selection_snapshot
        if (snapshot is None or self.last_selection_report.get('status') != 'intervention'
                or snapshot.cycle != self._active_selection_cycle
                or snapshot.task_version != 'task_sha256_' + _hash(self.task)):
            self.last_gap_report['delivery_error'] = 'stale_selection_snapshot'
            return False
        try:
            active = self._active_records()
        except ValueError:
            self.last_gap_report['delivery_error'] = 'committed_revision_content_mismatch'
            return False
        for selected in self.last_selection_report.get('selected', ()):
            if selected['id'] is None:
                continue
            frozen = next((row for row in snapshot.items if row.id == selected['id']), None)
            if frozen is None or active.get(frozen.id) != frozen:
                self._active_selection_cycle = None
                self.last_gap_report['delivery_error'] = 'selection_revision_revoked'
                return False
        return True
