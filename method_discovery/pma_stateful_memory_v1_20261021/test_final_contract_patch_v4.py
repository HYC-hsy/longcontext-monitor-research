"""V4 executable contract examples; no network transport or real task."""

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from . import prompts
from .audit import AuditCodec, validate_audit_result
from .proposal import build_candidate
from .reminder import validate_selection
from .schema import validate_snapshot
from .source import ContractError, SourceCatalog, canonical
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf
from .test_proposal import proposal
from .test_schema_advanced import rich_state, ref


class PromptContractV4Tests(unittest.TestCase):
    def setUp(self):
        self.base, self.ledger = rich_state()
        self.catalog = SourceCatalog(self.ledger, 'v4')
        self.wire = {}
        for key, source in self.ledger.items():
            span = self.catalog.add(key, 0, len(source['text']), 'maintenance')
            self.wire[key] = {'evidence_id': span.evidence_id,
                              'quote': source['text']}
        self.visible = {('entity', 'e'), ('state', 's'), ('requirement', 'req'),
                        ('gap', 'ge'), ('gap', 'ga')}

    def build(self, patch):
        patch['base_state_version'] = self.base['state_version']
        return build_candidate(proposal=patch, base=self.base,
            catalog=self.catalog, cycle_id='v4', processed_to=0,
            goal_ledger={'epoch': 1, 'deltas': {}, 'messages': ['u0']},
            visible_existing_ids=self.visible, archive={})

    def wire_body(self, body):
        if isinstance(body, list):
            return [self.wire_body(item) for item in body]
        if isinstance(body, dict):
            if set(body) == {'source_id', 'start', 'end', 'quote'}:
                return deepcopy(self.wire[body['source_id']])
            return {key: self.wire_body(value) for key, value in body.items()}
        return body

    def test_requirement_and_retirement_arrays_and_roles(self):
        patch = proposal()
        requirement = self.wire_body(self.base['B']['G']['specifications'][0])
        requirement.update(requirement_id='@replacement')
        old = self.wire_body(self.base['B']['G']['specifications'][0])
        old.update(requirement_id='@retired', status='superseded', retirement={
            'kind': 'interpretation_replaced', 'replacement_requirement_refs': [{
                'type': 'requirement', 'requirement_id': '@replacement',
                'revision': 1, 'task_version': 1}], 'source_refs': [self.wire['u0']]})
        patch['specification_upserts'] = [requirement, old]
        self.build(patch)
        for index, field in ((0, 'source_refs'), (1, 'source_refs'),
                             (1, 'replacement_requirement_refs')):
            for bad_value in ([], [self.wire['tool']]) if field == 'source_refs' else ([],):
                bad = deepcopy(patch)
                target = (bad['specification_upserts'][index] if index == 0 else
                          bad['specification_upserts'][index]['retirement'])
                target[field] = bad_value
                with self.subTest(index=index, field=field, value=bad_value):
                    with self.assertRaises(ContractError):
                        self.build(bad)

    def test_procedural_action_and_lesson_contract(self):
        action = leaf('execute', source_id='action', source_kind='executed_action')
        self.ledger['action'] = action
        snapshot = deepcopy(self.base)
        state = snapshot['B']['W']['states'][0]
        condition = deepcopy(state.pop('claim'))
        condition['time_role'] = 'past_episode'
        state.update(kind='procedural', episode={'conditions': condition,
            'action_text': 'execute', 'action_refs': [ref('action', 'execute')],
            'result': deepcopy(condition), 'time_role': 'past_episode'}, lesson={
                **deepcopy(condition), 'assertion_origin': 'inference',
                'time_role': 'general_hypothesis'})
        validate_snapshot(snapshot, self.ledger)
        for field, value in (('action_refs', []),
                             ('action_refs', [ref('tool', 'feature absent')]),
                             ('lesson_support', [])):
            bad = deepcopy(snapshot)
            obj = bad['B']['W']['states'][0]
            if field == 'lesson_support':
                obj['lesson']['support_refs'] = value
            else:
                obj['episode'][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ContractError):
                    validate_snapshot(bad, self.ledger)

    def test_gap_goal_and_closure_evidence_contract(self):
        for kind in ('tool_result', 'user_report', 'agent_report', 'executed_action'):
            self.ledger[kind] = leaf(kind, source_id=kind, source_kind=kind)
        snapshot = deepcopy(self.base)
        gap = snapshot['B']['DeltaE'][0]
        gap.update(status='supported', closure={'kind': 'environment_supported',
            'conclusion': 'known locally', 'evidence_refs': [ref('tool', 'feature absent')],
            'state_refs': []})
        for kind in ('tool_result', 'user_report', 'agent_report', 'executed_action'):
            gap['closure']['evidence_refs'] = [ref('tool', 'feature absent'), ref(kind, kind)]
            validate_snapshot(snapshot, self.ledger)
        for evidence in ([], [ref('u0', 'task')], [ref('agent_report', 'agent_report')],
                         [ref('executed_action', 'executed_action')]):
            gap['closure']['evidence_refs'] = evidence
            with self.subTest(evidence=evidence), self.assertRaises(ContractError):
                validate_snapshot(snapshot, self.ledger)
        gap['closure']['evidence_refs'] = [ref('tool', 'feature absent')]
        gap['goal_refs'] = []
        with self.assertRaisesRegex(ContractError, 'gap_missing_goal'):
            validate_snapshot(snapshot, self.ledger)

    def test_versions_direct_predecessor_and_local_scope(self):
        for kind, key, collection in (
                ('state', 'record_id', self.base['B']['W']['states']),
                ('requirement', 'requirement_id', self.base['B']['G']['specifications']),
                ('gap', 'gap_id', self.base['B']['DeltaE'])):
            name = {'state': 'state_upserts', 'requirement': 'specification_upserts',
                    'gap': 'gap_upserts'}[kind]
            for new in (False, True):
                patch = proposal()
                body = self.wire_body(collection[0])
                if new:
                    body[key] = '@new'
                body['revision'] = 2 if new else 1
                destination = patch['world_patch'] if kind == 'state' else patch
                destination[name] = [body]
                with self.subTest(kind=kind, new=new), self.assertRaisesRegex(
                        ContractError, 'new_object_revision|version_mismatch'):
                    self.build(patch)
        patch = proposal()
        body = self.wire_body(self.base['B']['W']['states'][0])
        body['revision'] = 2
        patch['world_patch']['state_upserts'] = [body]
        with self.assertRaisesRegex(ContractError, 'missing_direct_supersedes'):
            self.build(patch)
        body['supersedes'] = [{'type': 'state', 'record_id': 's', 'revision': 1}]
        self.build(patch)
        body.update(record_id='@new', revision=1, supersedes=[], entity_id='@entity')
        body['scope']['entity_ids'] = ['@entity']
        patch['world_patch']['entity_upserts'] = [{'entity_id': '@entity',
            'entity_type': 'other', 'display_name': 'same proposal'}]
        built = self.build(patch)
        self.assertEqual(built['candidate']['B']['W']['states'][-1]['scope'][
            'entity_ids'], [built['local_id_map']['@entity']])
        body['scope']['entity_ids'] = []
        with self.assertRaisesRegex(ContractError, 'unknown_scope_entity'):
            self.build(patch)

    def test_allowed_empty_arrays_and_required_operations(self):
        self.build(proposal())
        patch = proposal()
        body = self.wire_body(self.base['B']['W']['states'][0])
        body.update(record_id='@inference', revision=1)
        body['claim'].update(assertion_origin='inference', time_role='general_hypothesis',
                             support_refs=[], challenge_refs=[])
        patch['world_patch']['state_upserts'] = [body]
        self.build(patch)
        body['claim']['assertion_origin'] = 'tool_observation'
        with self.assertRaisesRegex(ContractError, 'missing_source_ref'):
            self.build(patch)
        del patch['world_patch']['record_transitions']
        with self.assertRaisesRegex(ContractError, 'schema_fields'):
            self.build(patch)

    def test_audit_target_revisions_and_field_path_syntax(self):
        view = AuditCodec().encode(self.base, self.base, binding={'cycle_id': 'v4'},
            sources=[], observations={}, operation_index=[], resolve_manifest=[])
        target = {'snapshot': 'candidate', 'target': {'kind': 'state', 'id': 's',
            'revision': 1}, 'field_path': 'claim.support_refs.0.quote'}
        result = {'protocol': 'audit-result/1', 'binding': view['binding'],
            'coverage': view['required_coverage'], 'outcome': 'issues', 'issues': [{
                'issue_id': 'v4', 'kind': 'observation_conflict', 'target': target,
                'related_targets': [], 'explanation': 'developer example',
                'witnesses': [{'kind': 'field', 'field': target,
                               'exact_value': 'feature absent'}],
                'repair_constraint': 'check observation'}],
            'closure_assessments': [], 'unusable_reason': None}
        validate_audit_result(result, view=view, catalog=self.catalog)
        for path in ('/claim/support_refs/0/quote', '$root', 'claim.support_refs[0].quote'):
            bad = deepcopy(result)
            bad['issues'][0]['target']['field_path'] = path
            with self.subTest(path=path), self.assertRaisesRegex(
                    ContractError, 'invalid_field_path'):
                validate_audit_result(bad, view=view, catalog=self.catalog)
        for kind, identifier, path in (('state', 's', 'claim.text'),
                ('requirement', 'req', 'interpretation'), ('gap', 'ge', 'target')):
            bad = deepcopy(result)
            bad['issues'][0]['target'] = {'snapshot': 'candidate', 'target': {
                'kind': kind, 'id': identifier}, 'field_path': path}
            with self.subTest(kind=kind), self.assertRaisesRegex(ContractError, 'version_mismatch'):
                validate_audit_result(bad, view=view, catalog=self.catalog)

    def test_selection_counts_uniqueness_binding_and_note(self):
        selected = [{'type': 'state', 'record_id': 's', 'revision': 1}]
        silent = {'decision': 'silent', 'state_version': 1, 'task_version': 1,
                  'phase2_view_id': 'v4'}
        remind = {**silent, 'decision': 'remind', 'refs': selected,
                  'context_for_action': 'If useful, check this observation.'}
        def check(value):
            return validate_selection(value, snapshot=self.base, phase2_view_id='v4',
                                      selected_refs=selected)
        check(silent)
        check(remind)
        for change in ({'refs': []}, {'refs': selected * 2}, {'refs': selected * 4},
                {'state_version': 0}, {'task_version': 2}, {'phase2_view_id': 'old'},
                {'context_for_action': ''}, {'context_for_action': 'x' * 1201},
                {'refs': [{'type': 'state', 'record_id': 's', 'revision': 0}]}):
            with self.subTest(change=change), self.assertRaises(ContractError):
                check({**remind, **change})
        with self.assertRaises(ContractError):
            check({**silent, 'refs': []})

    def test_role_messages_receive_rules(self):
        for builder, clauses in ((prompts.maintenance, ('Requirement.source_refs | no',
                'base revision+1', 'same-proposal @local', 'canonical retirement')),
                (prompts.audit, ('targets require revision', 'claim.support_refs.0.quote',
                 'does not mechanically require equality', 'ClosureAssessment=')),
                (prompts.selection, ('one to three', 'nonempty conditional advisory',
                 '1200 Unicode', '16384 UTF-8'))):
            messages = builder({'binding': 'developer example'})
            self.assertEqual(messages[0]['role'], 'system')
            for clause in clauses:
                self.assertIn(clause, messages[0]['content'])
            self.assertIn('GoalDeltaRef=', messages[0]['content'])
            self.assertIn('GapRef=', messages[0]['content'])


class InitializationV4Tests(unittest.TestCase):
    def test_empty_initialization_is_idempotent_and_retains_original_task(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'db'
            store = MemoryStore(path)
            initial = empty_snapshot()
            store.initialize(initial, leaf('task'))
            store.initialize(deepcopy(initial), leaf('task'))
            self.assertEqual(store.sources()['u0']['text'], 'task')
            self.assertEqual(store.goals(), {'epoch': 1, 'deltas': {}, 'messages': ['u0']})
            store.close()
            reopened = MemoryStore(path)
            self.assertEqual(reopened.snapshot(), initial)
            reopened.close()

    def test_nonempty_and_wrong_initial_values_fail_before_any_write(self):
        rich, _ = rich_state()
        seeds = [rich]
        cycle = empty_snapshot()
        for rid, replacement in (('r1', 'r2'), ('r2', 'r1')):
            cycle['B']['G']['specifications'].append({'requirement_id': rid,
                'revision': 1, 'task_version': 1, 'interpretation': rid,
                'source_refs': [ref('u0', 'task')], 'status': 'superseded',
                'retirement': {'kind': 'interpretation_replaced', 'source_refs': [ref('u0', 'task')],
                    'replacement_requirement_refs': [{'type': 'requirement',
                        'requirement_id': replacement, 'revision': 1, 'task_version': 1}]}})
        seeds.append(cycle)
        for path, value in ((('B', 'G', 'task_version'), 2),
                (('state_version',), 1), (('committed_event_seq',), 1),
                (('B', 'G', 'goal_deltas'), [{}]), (('B', 'W', 'entities'), [{}]),
                (('B', 'W', 'states'), [{}]), (('B', 'W', 'relations'), [{}]),
                (('B', 'DeltaE'), [{}]), (('B', 'DeltaA'), [{}]), (('B', 'F'), {})):
            seed = empty_snapshot()
            target = seed
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            seeds.append(seed)
        for seed in seeds:
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as root:
                store = MemoryStore(Path(root) / 'db')
                try:
                    with self.assertRaisesRegex(ContractError, 'invalid_initial_snapshot'):
                        store.initialize(seed, leaf('task'))
                    self.assertIsNone(store.snapshot())
                    for table in ('sources', 'singleton', 'archive', 'commits', 'commit_versions'):
                        self.assertEqual(store.db.execute('SELECT count(*) FROM ' + table).fetchone()[0], 0)
                    store.initialize(empty_snapshot(), leaf('task'))
                    self.assertEqual(store.sources()['u0']['text'], 'task')
                finally:
                    store.close()


class CommitRetryV4Tests(unittest.TestCase):
    def test_original_fingerprint_retries_after_head_advances_and_restart(self):
        from .test_core_contract_closure_v3 import seeded_store
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'db'
            store = seeded_store(path)
            base = store.snapshot()
            catalog = SourceCatalog(store.sources(), 'v4-retry')
            span = catalog.add('tool-2', 0, len('next result'), 'maintenance')
            patch = proposal('u1')
            patch['base_state_version'] = base['state_version']
            patch['world_patch']['record_transitions'] = [{
                'record_ref': {'type': 'state', 'record_id': 's', 'revision': 1},
                'to_status': 'contested', 'reason': 'new observation',
                'evidence_refs': [{'evidence_id': span.evidence_id, 'quote': 'next result'}]}]
            built = build_candidate(proposal=patch, base=base, catalog=catalog,
                cycle_id='u1', processed_to=2, goal_ledger=store.goals(),
                visible_existing_ids={('state', 's')}, archive=store.archive())
            original = {'update_id': built['update_id'], 'cycle_id': 'u1',
                'base': base, 'candidate': built['candidate'],
                'archive_delta': built['archive_delta'],
                'transition_changes': built['transition_changes']}
            u1 = store.compare_and_swap(**original)
            patch2 = proposal('u2')
            patch2['base_state_version'] = built['candidate']['state_version']
            u2 = build_candidate(proposal=patch2, base=store.snapshot(), catalog=catalog,
                cycle_id='u2', processed_to=2, goal_ledger=store.goals(),
                visible_existing_ids=set(), archive=store.archive())
            store.compare_and_swap(update_id=u2['update_id'], cycle_id='u2',
                base=store.snapshot(), candidate=u2['candidate'],
                archive_delta=u2['archive_delta'], transition_changes=u2['transition_changes'])
            head = store.snapshot()
            self.assertEqual(head['state_version'], 3)
            self.assertEqual(store.compare_and_swap(**original), u1)
            store.close()
            store = MemoryStore(path)
            try:
                self.assertEqual(store.compare_and_swap(**original), u1)
                self.assertEqual(store.snapshot(), head)
                for field, value in (('reason', 'another reason'), ('evidence_refs', [])):
                    altered = deepcopy(original)
                    altered['transition_changes'][0][field] = value
                    with self.subTest(field=field), self.assertRaisesRegex(
                            ContractError, 'update_id_identity_conflict'):
                        store.compare_and_swap(**altered)
                self.assertIn(('s', 1), store.archive())
            finally:
                store.close()

    def test_committed_historical_retirement_chain_survives_reopen(self):
        from .test_core_contract_closure_v3 import seeded_store
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'db'
            store = seeded_store(path, retired_requirement=True)
            base = store.snapshot()
            catalog = SourceCatalog(store.sources(), 'v4-history')
            span = catalog.add('u0', 0, 4, 'maintenance', exact_stored_ref=True)
            patch = proposal('history')
            patch['base_state_version'] = base['state_version']
            replacement = deepcopy(base['B']['G']['specifications'][1])
            replacement.update(revision=2, interpretation='revised interpretation',
                               source_refs=[{'evidence_id': span.evidence_id, 'quote': 'task'}])
            patch['specification_upserts'] = [replacement]
            for gap in base['B']['DeltaE'] + base['B']['DeltaA']:
                updated = deepcopy(gap)
                updated['revision'] += 1
                updated['goal_refs'][0]['revision'] = 2
                patch['gap_upserts'].append(updated)
            built = build_candidate(proposal=patch, base=base, catalog=catalog,
                cycle_id='history', processed_to=2, goal_ledger=store.goals(),
                visible_existing_ids={('requirement', 'replacement'), ('gap', 'ge'),
                                      ('gap', 'ga'), ('state', 's')}, archive=store.archive())
            store.compare_and_swap(update_id=built['update_id'], cycle_id='history',
                base=base, candidate=built['candidate'], archive_delta=built['archive_delta'])
            store.close()
            reopened = MemoryStore(path)
            try:
                snapshot = reopened.snapshot()
                validate_snapshot(snapshot, reopened.sources(), reopened.archive(),
                                  reopened.goals()['deltas'])
                retirement = snapshot['B']['G']['specifications'][0]['retirement']
                self.assertEqual(retirement['replacement_requirement_refs'][0]['revision'], 1)
                self.assertIn(('requirement', 'replacement', 1), reopened.archive())
            finally:
                reopened.close()


class ActualMessagesV4Tests(unittest.TestCase):
    def test_actual_role_messages_include_rules_in_measured_budget(self):
        import json
        from .budget import TokenProxy
        from .engine import CycleEngine
        from .test_engine import ScriptedProvider
        with tempfile.TemporaryDirectory() as root:
            store = MemoryStore(Path(root) / 'db')
            try:
                store.initialize(empty_snapshot(), leaf('task'))
                provider = ScriptedProvider()
                proxy = TokenProxy()
                result = CycleEngine(store, provider, task_text='task', token_proxy=proxy).run('v4-messages')
                self.assertEqual(result['status'], 'committed_selection_silent')
                expected = {'maintenance': 'Requirement.source_refs | no',
                            'audit': 'claim.support_refs.0.quote', 'selection': 'one to three'}
                prepared = {row['body']['role']: row['body']['input_size'] for row in
                    store.journal_rows(result['cycle_id']) if row['phase'] == 'call_prepared'}
                self.assertEqual(set(expected), {call['role'] for call in provider.calls})
                for call in provider.calls:
                    self.assertIn(expected[call['role']], call['messages'][0]['content'])
                    self.assertEqual(prepared[call['role']], proxy.measure(call['messages']))
                    self.assertGreater(prepared[call['role']]['proxy_tokens'],
                        proxy.measure([call['messages'][1]])['proxy_tokens'])
                    json.loads(call['messages'][1]['content'])
            finally:
                store.close()
