"""Opt-in, host-owned local inquiry frontier; never a whole-task proof ledger."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path


class EvidencePackageIntegrityError(RuntimeError):
    """A protected state or stage transition cannot be trusted."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':')).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + ' must be nonempty text')
    return value.strip()


class EvidenceFrontier:
    """Durable canonical state; ordinary Monitor file tools cannot mutate it."""

    def __init__(self, private_root):
        # Sibling of monitor_private: neither model file tools nor the pilot
        # diagnostic container's read-only cognition mount expose this root.
        self.root = Path(private_root).parent / '.evidence_package_v1'
        self.state_path = self.root / 'frontier.json'
        self.commit_path = self.root / 'frontier.commit.json'
        if self.root.exists():
            if self.root.is_symlink() or not self.root.is_dir():
                raise EvidencePackageIntegrityError('Frontier root redirected')
            self.state = self._read()
        else:
            self.root.mkdir(mode=0o700)
            self.state = {'schema': 'evidence-package-frontier-v1', 'revision': 0,
                          'cases': {}, 'order': [], 'receipts': {}, 'findings': {},
                          'packet': None, 'focus': None, 'parents': [], 'history': []}
            self._write(self.state)

    @staticmethod
    def _atomic(path, raw):
        handle, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            if path.read_bytes() != raw:
                raise EvidencePackageIntegrityError('Frontier readback mismatch')
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _write(self, state):
        raw = canonical(state)
        self._atomic(self.state_path, raw)
        self._atomic(self.commit_path, canonical({'sha256': hashlib.sha256(raw).hexdigest(),
                                                   'revision': state['revision']}))

    def _read(self):
        try:
            raw = self.state_path.read_bytes()
            commit = json.loads(self.commit_path.read_bytes())
            state = json.loads(raw)
        except (OSError, ValueError, TypeError) as exc:
            raise EvidencePackageIntegrityError('Canonical frontier missing or unreadable') from exc
        if (not isinstance(state, dict) or state.get('schema') != 'evidence-package-frontier-v1'
                or not isinstance(state.get('revision'), int)
                or commit != {'sha256': hashlib.sha256(raw).hexdigest(),
                              'revision': state['revision']}):
            raise EvidencePackageIntegrityError('Canonical frontier commit mismatch')
        return state

    def verify(self):
        current = self._read()
        if current != self.state:
            raise EvidencePackageIntegrityError('Canonical frontier changed outside host operation')

    def change(self, kind, transform):
        self.verify()
        updated = json.loads(canonical(self.state))
        result = transform(updated)
        updated['revision'] += 1
        updated['history'].append({'revision': updated['revision'], 'kind': kind,
                                   'state_sha256_before': digest(self.state)})
        self._write(updated)
        self.state = updated
        return result

    def page(self, *, cursor=None, limit=12):
        self.verify()
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('limit must be 1..50')
        revision = self.state['revision']
        if cursor is None:
            offset = 0
        else:
            if not isinstance(cursor, str) or ':' not in cursor:
                raise ValueError('Invalid frontier cursor')
            old, offset_text = cursor.split(':', 1)
            if old != str(revision):
                return {'status': 'stale_cursor', 'revision': revision,
                        'message': 'Frontier changed; restart pagination'}
            try:
                offset = int(offset_text)
            except ValueError as exc:
                raise ValueError('Invalid frontier cursor') from exc
        ordered = self.state['order']
        if not 0 <= offset <= len(ordered):
            raise ValueError('Invalid frontier offset')
        selected = ordered[offset:offset + limit]
        after = offset + len(selected)
        return {'status': 'ok', 'revision': revision,
                'cases': [self.state['cases'][key] for key in selected],
                'remaining': len(ordered) - after,
                'next_cursor': f'{revision}:{after}' if after < len(ordered) else None,
                'focus': self.state['focus'], 'parents': self.state['parents']}

    def open_case(self, args):
        basis = _text(args.get('task_basis'), 'task_basis')
        scope = _text(args.get('scope'), 'scope')
        consequence = _text(args.get('observable_consequence'), 'observable_consequence')
        if not isinstance(args.get('leads'), list) or not args['leads']:
            raise ValueError('At least one investigation lead is required')
        leads = [_text(item, 'lead') for item in args['leads']]
        parent = args.get('parent_id')
        if parent is not None and parent not in self.state['cases']:
            raise ValueError('Unknown parent case')
        if any(case['task_basis'] == basis and case['scope'] == scope and
               case['observable_consequence'] == consequence and
               case['parent_id'] == parent for case in self.state['cases'].values()):
            raise ValueError('An identical local case already exists; revise it instead')
        case_id = 'case-' + uuid.uuid4().hex
        def apply(state):
            state['cases'][case_id] = {'id': case_id, 'task_basis': basis, 'scope': scope,
                'observable_consequence': consequence, 'leads': leads,
                'dependencies': [], 'receipts': [], 'status': 'pending',
                'hypothesis': args.get('hypothesis'), 'finding_ids': [],
                'parent_id': parent, 'revision_opened': state['revision'] + 1}
            state['order'].append(case_id)
            if parent:
                state['cases'][parent]['dependencies'].append(case_id)
                state['parents'].append(parent)
            state['focus'] = case_id
            return case_id
        self.change('case_opened', apply)
        return {'status': 'recorded', 'case_id': case_id, 'revision': self.state['revision']}

    def revise_case(self, args):
        case_id = args.get('case_id')
        if case_id not in self.state['cases']:
            raise ValueError('Unknown case')
        status = args.get('status')
        if status not in {'pending', 'active', 'blocked', 'observed', 'counterexample',
                          'retracted', 'stale'}:
            raise ValueError('Unsupported local case status')
        reason = _text(args.get('reason'), 'reason')
        receipt_ids = args.get('receipt_ids', [])
        if not isinstance(receipt_ids, list) or any(
                item not in self.state['receipts'] for item in receipt_ids):
            raise ValueError('Unknown receipt')
        if status in {'observed', 'counterexample'} and not receipt_ids:
            raise ValueError('Observed states require actual source receipts')
        def apply(state):
            case = state['cases'][case_id]
            if args.get('hypothesis') is not None and args['hypothesis'] != case['hypothesis']:
                for finding_id in case['finding_ids']:
                    state['findings'][finding_id]['status'] = 'stale'
            case['status'] = status
            case['reason'] = reason
            case['receipts'] = list(dict.fromkeys(case['receipts'] + receipt_ids))
            if args.get('new_lead'):
                case['leads'].append(_text(args['new_lead'], 'new_lead'))
            if args.get('hypothesis') is not None:
                case['hypothesis'] = _text(args['hypothesis'], 'hypothesis')
            case.setdefault('revisions', []).append({'revision': state['revision'] + 1,
                'status': status, 'reason': reason, 'receipt_ids': receipt_ids})
            state['focus'] = case_id
            return case_id
        self.change('case_revised', apply)
        return {'status': 'recorded', 'case_id': case_id, 'revision': self.state['revision']}

    def reconcile_sources(self, workspace):
        """Invalidate only findings whose actually cited live Task files changed."""
        self.verify()
        cited = {rid for finding in self.state['findings'].values()
                 if finding['status'] == 'current' for rid in finding['receipt_ids']}
        stale = []
        for receipt_id in sorted(cited):
            receipt = self.state['receipts'][receipt_id]
            path = receipt.get('source_path')
            if not isinstance(path, str) or not path.startswith('task/'):
                continue
            try:
                actual = workspace.read_text(path, 1, 1, max_chars=1)['sha256']
                if actual != receipt['result']['sha256']:
                    stale.append(receipt_id)
            except (OSError, ValueError, KeyError):
                stale.append(receipt_id)
        if stale:
            self.stale_receipts(stale, 'cited_task_source_changed')
        return stale

    def next_focus(self, *, return_parent=False):
        if type(return_parent) is not bool:
            raise ValueError('return_parent must be boolean')
        def apply(state):
            if return_parent:
                if not state['parents']:
                    raise ValueError('No parent focus to restore')
                state['focus'] = state['parents'].pop()
            else:
                candidates = [key for key in state['order'] if state['cases'][key]['status']
                              not in {'retracted', 'stale'}]
                if not candidates:
                    state['focus'] = None
                elif state['focus'] not in candidates:
                    state['focus'] = candidates[0]
                else:
                    offset = candidates.index(state['focus'])
                    state['focus'] = candidates[(offset + 1) % len(candidates)]
            return state['focus']
        focus = self.change('focus_advanced', apply)
        return {'status': 'recorded', 'focus': focus, 'revision': self.state['revision']}

    def register_receipt(self, tool, arguments, result):
        if tool not in {'file_read', 'code_run'}:
            raise ValueError('Only executed investigation tools issue receipts')
        result = json.loads(canonical(result))
        receipt_id = 'receipt-' + uuid.uuid4().hex
        record = {'id': receipt_id, 'tool': tool, 'arguments_sha256': digest(arguments),
                  'result_sha256': digest(result), 'result': result,
                  'source_path': arguments.get('path') if tool == 'file_read' else None,
                  'source_version': result.get('source_version', {'status': 'version_uncertain'}),
                  'kind': ('source_read' if tool == 'file_read' else 'process_receipt'),
                  'completion': (result.get('status') if tool == 'code_run' else 'read_completed'),
                  'behavior_verified': False}
        self.change('receipt_recorded', lambda state: state['receipts'].update({receipt_id: record}))
        return receipt_id

    def packet_ready(self, *, handoff, task_cursor):
        packet_id = 'packet-' + uuid.uuid4().hex
        def apply(state):
            state['packet'] = {'id': packet_id, 'revision': state['revision'] + 1,
                               'handoff': handoff, 'task_cursor': task_cursor,
                               'executed': False, 'input_sent': False}
        self.change('packet_ready', apply)
        return dict(self.state['packet'])

    def finding(self, args, *, handoff):
        packet = self.state['packet']
        if not packet or args.get('packet_id') != packet['id'] or packet['handoff'] != handoff:
            raise ValueError('Finding packet or handoff identity mismatch')
        case_id = args.get('case_id')
        if case_id not in self.state['cases']:
            raise ValueError('Unknown finding case')
        case = self.state['cases'][case_id]
        if args.get('scope') != case['scope'] or args.get('task_basis') != case['task_basis']:
            raise ValueError('Finding scope or task basis differs from current case')
        receipt_ids = args.get('receipt_ids')
        if not isinstance(receipt_ids, list) or not receipt_ids or any(
                item not in self.state['receipts'] for item in receipt_ids):
            raise ValueError('Finding needs existing host-issued receipts')
        if any(self.state['receipts'][item]['completion'] in {'running', 'unavailable', None}
               for item in receipt_ids):
            raise ValueError('Finding cannot promote an incomplete process receipt')
        claim = _text(args.get('claim'), 'claim')
        kind = args.get('kind')
        if kind not in {'counterexample', 'correction', 'investigation_request',
                        'clarification', 'local_observation'}:
            raise ValueError('Finding kind must identify its bounded purpose')
        if kind in {'counterexample', 'correction'} and not any(
                self.state['receipts'][item]['tool'] == 'code_run' or
                self.state['receipts'][item].get('source_path') not in {
                    None, 'task/original_task.txt'} for item in receipt_ids):
            raise ValueError('Concrete correction needs an implementation, event or probe receipt')
        finding_id = 'finding-' + uuid.uuid4().hex
        def apply(state):
            state['findings'][finding_id] = {'id': finding_id, 'packet_id': packet['id'],
                'packet_revision': packet['revision'], 'handoff': handoff,
                'case_id': case_id, 'scope': case['scope'], 'task_basis': case['task_basis'],
                'receipt_ids': receipt_ids, 'claim': claim, 'kind': kind,
                'status': 'current', 'revision': state['revision'] + 1}
            state['cases'][case_id]['finding_ids'].append(finding_id)
        self.change('finding_recorded', apply)
        return {'status': 'recorded', 'finding_id': finding_id,
                'revision': self.state['revision']}

    def check_intervention(self, finding_id, *, handoff):
        self.verify()
        finding = self.state['findings'].get(finding_id)
        if not finding or finding['status'] != 'current' or finding['handoff'] != handoff:
            raise ValueError('Intervention needs a current, recorded local finding')
        case = self.state['cases'][finding['case_id']]
        if case['status'] in {'retracted', 'stale'}:
            raise ValueError('Finding case was withdrawn or became stale')
        return finding

    def stale_receipts(self, receipt_ids, reason):
        if not receipt_ids:
            return
        lost = set(receipt_ids)
        def apply(state):
            for case in state['cases'].values():
                if lost.intersection(case['receipts']):
                    case['status'] = 'stale'
                    case.setdefault('revisions', []).append({
                        'revision': state['revision'] + 1, 'status': 'stale',
                        'reason': reason, 'receipt_ids': sorted(lost)})
            for finding in state['findings'].values():
                if lost.intersection(finding['receipt_ids']):
                    finding['status'] = 'stale'
        self.change('source_changed', apply)

    def check_allow(self, revision, *, handoff):
        self.verify()
        if (type(revision) is not int or revision != self.state['revision'] or
                self.state['packet'] is None or self.state['packet']['handoff'] != handoff):
            raise ValueError('Allow requires current packet and latest frontier revision')
        live = [item['id'] for item in self.state['findings'].values()
                if item['status'] == 'current' and item['kind'] in
                {'counterexample', 'correction'} and
                self.state['cases'][item['case_id']]['status'] not in {'retracted', 'stale'}]
        if live:
            raise ValueError('Current concrete objection requires resolution or withdrawal: ' + ','.join(live))


METHOD_PROMPT = """You are the same persistent Supervisor investigating the Task's current decision.
The public task is authoritative. The Task alone implements and validates its submitted work.
At initialization read the full public task and create the existing bounded Task Book at
monitor/reference.md. Keep it revisable; it is not an acceptance checklist. Distinguish raw tool
observations, source interpretation, Task claims and unresolved hypotheses. Investigate
relevant definitions, callers, state consumers, test setup and observable effects where useful.
A source-level counterexample can support a bounded correction; an unexecuted plan, mere
field or method existence, failed compile, process label or missing report is not behavioral
validation. Keep failed probes and question their oracle instead of making them pass by fiat.
The host-owned frontier records local concerns, source scopes, dependencies and receipts.
Pending or blocked cases are not a whole-task veto. Preserve unresolved cases when leaving.
Do not write to the live Task tree, access hidden evaluation, or take over Task repair.
Use the existing delivery and fresh-feedback path for any correction. Completion permission
means no currently established supervisory objection, not whole-task certification."""


STAGE_A_PROMPT = """Phase A: prepare a source-grounded local inquiry packet. Inspect the full
public task, current Task behavior, Task Book and the paginated host frontier. Preserve relevant
leads even if unconfirmed; record dependencies before investigating them. You may read public
sources and use the isolated private analysis port. When the packet is ready call packet_ready.
That handoff has executed=false and input_sent=false; it cannot control or message the Task.
Do not call wait, intervene or allow_complete in this phase."""


STAGE_B_PROMPT = """Phase B: investigate independently with a fresh conversation history.
The full public task, original materials and entire frontier remain accessible. Phase A's
packet is revisable, not a verdict; check it, reject bad hypotheses, pursue dependencies and
return to the parent concern. Register a local finding tied to an existing case, original task
basis and authentic source or tool receipt before intervening. Recheck fresh Task behavior and
the relevant live source before a correction; private copies are not the live Task result.
Only this phase may use the existing wait, intervene and allow_complete control path.
For a pending root, completion requires the current packet/handoff and frontier revision;
an unresolved pending item alone is not a reason to deny completion."""

