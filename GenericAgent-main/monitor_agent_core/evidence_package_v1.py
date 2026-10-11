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
        self.root = Path(private_root) / '.evidence_package_v1'
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

    def register_receipt(self, tool, arguments, result):
        if tool not in {'file_read', 'code_run'}:
            raise ValueError('Only executed investigation tools issue receipts')
        receipt_id = 'receipt-' + uuid.uuid4().hex
        record = {'id': receipt_id, 'tool': tool, 'arguments_sha256': digest(arguments),
                  'result_sha256': digest(result), 'result': result,
                  'source_version': result.get('source_version', {'status': 'version_uncertain'}),
                  'kind': ('source_read' if tool == 'file_read' else 'process_receipt'),
                  'completion': (result.get('status') if tool == 'code_run' else 'read_completed')}
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
        claim = _text(args.get('claim'), 'claim')
        finding_id = 'finding-' + uuid.uuid4().hex
        def apply(state):
            state['findings'][finding_id] = {'id': finding_id, 'packet_id': packet['id'],
                'packet_revision': packet['revision'], 'handoff': handoff,
                'case_id': case_id, 'scope': case['scope'], 'task_basis': case['task_basis'],
                'receipt_ids': receipt_ids, 'claim': claim,
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

    def check_allow(self, revision, *, handoff):
        self.verify()
        if (type(revision) is not int or revision != self.state['revision'] or
                self.state['packet'] is None or self.state['packet']['handoff'] != handoff):
            raise ValueError('Allow requires current packet and latest frontier revision')
        live = [item['id'] for item in self.state['cases'].values()
                if item['status'] == 'counterexample']
        if live:
            raise ValueError('Current concrete objection requires resolution or withdrawal: ' + ','.join(live))

