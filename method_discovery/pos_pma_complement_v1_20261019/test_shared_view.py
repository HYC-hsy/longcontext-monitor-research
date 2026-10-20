"""Offline shared-view order, freeze, audit and panel checks with pinned cores."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parent),
                str(ROOT / 'pos_upstream_ga_v1_20261017'),
                str(ROOT / 'pos_upstream_ga_v1_20261017/vendor'),
                str(ROOT / ('curator_supervisor_convergence_v0/'
                    'pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src'))]
from .test_candidate_core import INITIAL, UPDATE, Logger, SyncRole, AsyncRole, response
from episode import PoSEpisode, execution_config
from memory_agent.memory.trigger import MemoryAgentTrigger, TriggerConfig
from memory_agent.memory.universal_memory import UniversalMemory
from .memory_adapter import SharedViewMemoryAgent
from .shared_view import SharedViewBeliefManager, SharedViewEpisode, shared_panel


class EvidenceRole(SyncRole):
    """Translate legacy *fixture* steps into IDs actually shown in the request."""
    def __call__(self, messages):
        raw = super().__call__(messages)
        if '"evidence_id"' not in messages[1]['content']:
            return raw
        try:
            payload = json.loads(raw)
            audit = json.loads(messages[1]['content'].split('\nReturn JSON:', 1)[0])
            if not isinstance(payload, dict) or not isinstance(payload.get('issues'), list):
                return raw
            for issue in payload['issues']:
                if not isinstance(issue, dict) or 'evidence_step' not in issue:
                    continue
                step = issue.pop('evidence_step')
                quote = issue.get('evidence_quote')
                ids = [source['evidence_id'] for row in audit['raw_trajectory']
                    if type(step) is int and row['step'] == step
                    for source in row.get('citable_sources', ())
                    if isinstance(quote, str) and quote in source['text']]
                issue['evidence_id'] = ids[0] if ids else 'ev_not_visible'
            return json.dumps(payload)
        except (ValueError, TypeError, KeyError):
            return raw


def tool(name, arguments):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


class Tests(unittest.TestCase):
    def make(self, *, interval=1, initial_advice='<no_intervention/>'):
        log = Logger()
        belief = SyncRole([json.dumps(INITIAL), json.dumps(UPDATE)])
        consistency = EvidenceRole(['{"issues": []}', '{"issues": []}'])
        progress = SyncRole(['{"progress": 0, "score": 0.0, '
                             '"affected_record_ids": [], "reason": "no change"}'])
        pma = AsyncRole([response('', [tool('memory_save_knowledge',
            {'content': 'Remember actual tool output'})]), response(initial_advice),
            response(), response('<no_intervention/>')])
        pos = PoSEpisode(case_id='shared-test', config=execution_config(),
            logger=log, belief_call=belief, consistency_call=consistency,
            progress_call=progress, manager_class=SharedViewBeliefManager)
        bank = SharedViewMemoryAgent(llm=pma, memory=UniversalMemory())
        trigger = MemoryAgentTrigger(TriggerConfig(interval=interval,
                                                   trigger_on_first_step=True))
        episode = SharedViewEpisode(pos_episode=pos, memory_agent=bank,
            trigger=trigger, logger=log)
        return episode, belief, consistency, pma

    def test_phase_order_and_frozen_bank_panel(self):
        ep, belief, consistency, pma = self.make(initial_advice=
            '<context_for_action>Check the tool result.</context_for_action>')
        first = asyncio.run(ep.reset(task='Clean mug.',
                                     observation='Clean mug.', actions=[]))
        self.assertEqual(ep.phase1_status, 'completed')
        self.assertEqual(ep.phase2_status, 'reminder')
        self.assertEqual(len(pma.requests), 2)
        self.assertIn('Check the tool result.', first['panel'])
        self.assertIn('recovery', first['panel'])
        self.assertNotIn('memory_update_status', [item['function']['name']
            for item in pma.requests[0]['tools']])
        self.assertEqual(ep.memory.memory.status, '')
        task_only = ep.manager.sentinel._compact_trajectory([{
            'step': -1, 'action': None, 'observation': 'Clean mug.'}])
        self.assertEqual(task_only[0]['citable_sources'], [])
        self.assertEqual(task_only[0]['source_origin'],
                         'original_task_not_tool_result')
        self.assertEqual([row['phase'] for row in ep.memory.rendered_entry_ids],
                         ['phase1', 'shared_selection', 'phase2'])
        self.assertEqual(ep.memory.rendered_entry_ids[1]['knowledge'],
                         ep.memory.rendered_entry_ids[2]['knowledge'])
        ep.request_accepted(panel=first, event_id='accepted-task-1')
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-1',
                  'result': {'stdout': 'Mug is still dirty.'},
                  'next_prompt': 'NOT A TOOL CITATION'}
        asyncio.run(ep.update(actor_attempt=1, transition_id='joint-1',
            thought='Inspect', action_batch=[{'id': 'tool-1', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(len(belief.requests), 2)
        self.assertIn('shared_selection', json.dumps(belief.requests[1]))
        self.assertIn('tool-1', json.dumps(belief.requests[1]))
        self.assertEqual(ep.advice_history[0]['reviewed_transition'], 'joint-1')
        self.assertIn('accepted-task-1', pma.requests[-1]['prompt'])
        self.assertNotIn('Check the tool result.', ep.decision_panel(
            observation='Mug is still dirty.')['panel'])
        compact = ep.manager.sentinel._compact_trajectory([{
            'step': 0, 'action': None,
            'observation': 'Clean mug.'}])
        self.assertFalse(any('NOT A TOOL CITATION' in json.dumps(row)
                             for row in compact))

    def test_partial_bank_before_pos_initialization(self):
        ep, *_ = self.make()
        async def failing_call(**_kwargs):
            raise RuntimeError('synthetic Phase 1 failure')
        ep.memory.llm.call = failing_call
        with self.assertRaisesRegex(RuntimeError, 'synthetic Phase 1 failure'):
            asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                                 actions=[]))
        partial = ep.get_result()
        self.assertEqual(partial['phase1_status'], 'failed')
        self.assertEqual(partial['initialization_stage'], 'not_attempted')
        self.assertEqual(partial['pos']['status'], 'unavailable')
        self.assertEqual(partial['bank']['knowledge'], [])

    def test_interval_skip_selects_unchanged_bank_once(self):
        ep, belief, _, pma = self.make(interval=3)
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                             actions=[]))
        asyncio.run(ep.update(actor_attempt=1, transition_id='joint-skip',
            thought='Inspect', action_batch=[{'id': 'tool-1', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation='Mug remains dirty.', source_events=[]))
        self.assertEqual(ep.phase1_status, 'not_triggered')
        self.assertEqual(ep.phase2_status, 'not_triggered')
        self.assertEqual(len(pma.requests), 2)
        self.assertEqual(len(belief.requests), 2)
        self.assertEqual(ep.frozen_selection['bank_version'], 1)
        self.assertEqual([row['phase'] for row in ep.memory.rendered_entry_ids],
                         ['phase1', 'shared_selection', 'phase2',
                          'shared_selection'])

    def test_audit_uses_only_visible_tool_fields_and_one_step_budget(self):
        ep, *_ = self.make()
        sentinel = ep.manager.sentinel
        sentinel.shared_sources = ({'event_id': 'old-tool', 'origin': 'tool_result',
            'sha256': 'a' * 64, 'pos_step': 3,
            'raw': {'result': {'stdout': 'A' * 7000 + 'VISIBLE_TAIL'},
                    'next_prompt': 'FAKE_HOST_NOTE'}},
            {'event_id': 'initial-task', 'origin': 'original_task',
             'sha256': 'b' * 64, 'pos_step': None,
             'raw': {'result': {'stdout': 'TASK_NOT_TOOL'}}})
        compact = sentinel._compact_trajectory([])
        self.assertEqual(len(compact), 1)
        fields = compact[0]['citable_sources']
        self.assertLessEqual(sum(len(field['text']) for field in fields),
                             sentinel.audit_observation_max_chars)
        self.assertFalse(any('FAKE_HOST_NOTE' in field['text'] or
                             'TASK_NOT_TOOL' in field['text'] for field in fields))
        self.assertEqual(compact[0]['step'], 3)
        self.assertTrue(all(field['source_path'].startswith('old-tool:result.')
                            for field in fields))
        self.assertNotIn('A' * 7000, ''.join(field['text'] for field in fields))
        # The same event already present in the live window gets no second
        # allowance from its historical registry copy.
        current = sentinel._compact_trajectory([{'step': 3, 'action': None,
            'observation': json.dumps({'tool_results': [{
                'tool_use_id': 'old-tool', 'result': {'stdout': 'A' * 7000 +
                'VISIBLE_TAIL'}}]})}])
        self.assertEqual(len(current), 1)
        self.assertEqual(sum(len(field['text']) for field in current[0]['citable_sources']),
                         sentinel.audit_observation_max_chars)
        self.assertFalse(current[0].get('shared_history'))

    def test_two_distinct_events_at_same_step_and_memory_not_citable(self):
        ep, *_ = self.make()
        sentinel = ep.manager.sentinel
        sentinel.shared_selection = {'entries': [{'id': 'mem-1'}],
            'rendered_text': 'MEMORY_MIDDLE_ONLY', 'bank_version': 1}
        sources = ({'event_id': 'tool-A', 'origin': 'tool_result',
                    'sha256': 'a' * 64, 'pos_step': 2,
                    'raw': {'result': {'stdout': 'FIRST_SHORT'}}},
                   {'event_id': 'tool-B', 'origin': 'tool_result',
                    'sha256': 'b' * 64, 'pos_step': 2,
                    'raw': {'result': {'stdout': 'SECOND_DISTINCT'}}})
        sentinel.shared_sources = sources
        compact = sentinel._compact_trajectory([])
        self.assertEqual(len(compact), 1)
        self.assertEqual({item['event_id'] for item in compact[0]['shared_history']},
                         {'tool-A', 'tool-B'})
        self.assertIn('SECOND_DISTINCT', json.dumps(compact))
        original = {'step': 2, 'action': None, 'observation': json.dumps({
            'tool_results': [{'tool_use_id': 'tool-A',
                              'result': {'stdout': 'FIRST_SHORT'}}]})}
        merged = sentinel._compact_trajectory([original])
        self.assertEqual(len(merged), 1)
        self.assertEqual([item['event_id'] for item in merged[0]['shared_history']],
                         ['tool-B'])
        self.assertEqual(len([item for item in merged[0]['citable_sources']
            if 'FIRST_SHORT' in item['text']]), 1)
        from belief.beliefSentinel import SentinelIssue
        def issue(quote):
            return SentinelIssue(targets=['e1'], issue_type='contradiction',
                problem='test', evidence_step=2, evidence_quote=quote,
                evidence='test', suggestion='test')
        evidence = {2: sentinel._trajectory_text(merged[0])}
        self.assertTrue(sentinel._valid_issue(issue('SECOND_DISTINCT'), {'e1'}, evidence))
        self.assertFalse(sentinel._valid_issue(issue('MEMORY_MIDDLE_ONLY'), {'e1'}, evidence))
        sentinel.call_model.replies.append(json.dumps({
            'issues': [{'targets': ['e1'], 'issue_type': 'contradiction',
                'problem': 'memory prose cannot cite itself', 'evidence_step': 2,
                'evidence_quote': 'MEMORY_MIDDLE_ONLY', 'evidence': 'memory',
                'suggestion': 'ignore'}]}))
        findings = sentinel.audit_candidate(case_id='case', base_step=2, mode='local',
            belief_before={'world': {'entities': {'e1': {}}}},
            candidate_belief={'world': {'entities': {'e1': {}}}},
            raw_trajectory=[original])
        self.assertEqual(findings, [])
        submitted = [row for name, row in ep.logger.rows
                     if name == 'belief_sentinel_model_input'][-1]['messages']
        self.assertIn('MEMORY_MIDDLE_ONLY', json.dumps(submitted))
        self.assertIn('SECOND_DISTINCT', json.dumps(submitted))

    def test_phase2_uses_current_selection_sources_and_attempt_reset(self):
        ep, belief, consistency, pma = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        pma.replies[0] = response('', [tool('memory_save_knowledge',
            {'content': 'Memory from actual tool output'})])
        first = {'origin': 'GA_tool_outcome', 'tool_use_id': 'actual-1',
                 'result': {'stdout': 'WINDOW_OUTSIDE_SOURCE'}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='joint-1',
            thought='inspect', action_batch=[{'id': 'actual-1', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [first]}),
            source_events=[first]))
        self.assertIn('WINDOW_OUTSIDE_SOURCE', pma.requests[-1]['prompt'])
        prior_bank = ep.memory.memory.to_dict()
        prior_pos = ep.pos.get_result()
        async def fail_call(**_kwargs):
            raise RuntimeError('fatal next Phase 1')
        ep.memory.llm.call = fail_call
        with self.assertRaisesRegex(RuntimeError, 'fatal next Phase 1'):
            asyncio.run(ep.update(actor_attempt=2, transition_id='joint-2',
                thought='inspect', action_batch=[{'id': 'actual-2',
                    'name': 'inspect', 'arguments': {}, 'order': 0,
                    'status': 'executed'}], observation='Second actual result.'))
        result = ep.get_result()
        self.assertEqual(result['phase1_status'], 'failed')
        self.assertEqual(result['phase2_status'], 'not_attempted')
        self.assertIsNone(result['frozen_selection'])
        self.assertEqual(result['last_phase1_operations'], [])
        self.assertFalse(result['current_attempt']['reviewed'])
        self.assertEqual(result['bank'], prior_bank)
        self.assertEqual(result['pos'], prior_pos)
        self.assertTrue(any(row.get('kind') == 'transition_result_recorded' and
            row.get('transition_id') == 'joint-2' for row in result['events']))

    def test_partial_real_crud_survives_initialization_and_update_failure(self):
        for initialize in (True, False):
            with self.subTest(initialize=initialize):
                ep, _belief, _consistency, pma = self.make()
                if not initialize:
                    asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                                         actions=[]))
                failing_reply = response('', [
                    tool('memory_save_knowledge', {'content': 'Committed first item'}),
                    tool('memory_save_procedural', {'content': 'Fatal second item'})])
                pma.replies[0] = failing_reply
                def fail_second(_content):
                    raise RuntimeError('synthetic bank storage failure')
                ep.memory.memory.save_procedural = fail_second
                with self.assertRaisesRegex(RuntimeError, 'synthetic bank storage failure'):
                    if initialize:
                        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                                             actions=[]))
                    else:
                        asyncio.run(ep.update(actor_attempt=1,
                            transition_id='joint-partial', thought='inspect',
                            action_batch=[{'id': 'tool-partial', 'name': 'inspect',
                                'arguments': {}, 'order': 0, 'status': 'executed'}],
                            observation='Actual inspected result.',
                            source_events=[{'tool_use_id': 'tool-partial',
                                'result': {'stdout': 'Actual inspected result.'}}]))
                partial = ep.get_result()
                self.assertEqual(partial['phase1_status'], 'failed')
                self.assertEqual(partial['phase2_status'], 'not_attempted')
                self.assertIsNone(partial['frozen_selection'])
                self.assertEqual(len(partial['last_phase1_operations']), 1)
                self.assertEqual(len(partial['bank']['knowledge']),
                                 1 if initialize else 2)
                saved = partial['last_phase1_operations'][0]['memory_id']
                self.assertIn(saved, partial['entry_sources'])
                self.assertEqual(partial['current_attempt']['reviewed'], False)
                self.assertEqual(partial['current_attempt']['stage'], 'phase1_failed')
                if initialize:
                    self.assertEqual(partial['initialization_stage'], 'not_attempted')
                    self.assertEqual(partial['pos']['status'], 'unavailable')
                else:
                    self.assertEqual(partial['current_attempt']['kind'], 'transition')

    def test_repair_reaudit_receive_same_frozen_memory_in_actual_requests(self):
        ep, belief, consistency, pma = self.make()
        belief.replies.append(json.dumps(UPDATE))
        issue = {'targets': ['e1'], 'issue_type': 'contradiction',
                 'problem': 'Prior clean interpretation conflicts with actual tool',
                 'evidence_step': 0, 'evidence_quote': 'STILL_DIRTY',
                 'evidence': 'STILL_DIRTY', 'suggestion': 'retain gap'}
        consistency.replies[1:] = [json.dumps({'issues': [issue]}),
                                   '{"issues": []}']
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'repair-tool',
                  'result': {'stdout': 'STILL_DIRTY'}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='repair-transition',
            thought='Inspect', action_batch=[{'id': 'repair-tool', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(len(consistency.requests), 3)
        self.assertEqual(len(belief.requests), 3)
        for request in (belief.requests[1], consistency.requests[1],
                        belief.requests[2], consistency.requests[2]):
            self.assertIn('Remember actual tool output', json.dumps(request))
            self.assertIn('shared_selection', json.dumps(request))
        self.assertIn('STILL_DIRTY', json.dumps(consistency.requests[1]))
        self.assertIn('STILL_DIRTY', json.dumps(consistency.requests[2]))
        audit_meta = [row for name, row in ep.logger.rows
                      if name == 'shared_audit_history_input']
        self.assertEqual(audit_meta[-1]['selection_sha256'],
                         audit_meta[-2]['selection_sha256'])
        repair_body = json.dumps(belief.requests[2], ensure_ascii=False)
        self.assertIn('Rejected candidate', repair_body)
        self.assertIn('Original patch', repair_body)
        self.assertIn('replacement incremental patch', repair_body)
        self.assertIn('STILL_DIRTY', repair_body)
        self.assertIn('Current structured Belief', repair_body)

    def test_schema_repair_carries_each_actual_failed_response(self):
        ep, belief, _, _ = self.make()
        manager = ep.manager
        manager.max_json_retries = 2
        belief.replies = ['{first broken', '{second broken', json.dumps(INITIAL)]
        manager._request_json([{'role': 'user', 'content': 'original task'}],
                              operation='initialize', step=-1)
        self.assertIn('{first broken', belief.requests[1][-1]['content'])
        self.assertIn('{second broken', belief.requests[2][-1]['content'])
        self.assertIn('original task', json.dumps(belief.requests[2]))

    def test_cross_record_repair_binds_provider_raw_and_normalized_patch(self):
        ep, belief, _, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        bad = deepcopy(UPDATE)
        bad['upsert_relations'] = [{'relation_id': 'r-new', 'source': 'e1',
            'target': 'missing-owner', 'relation_type': 'synthetic relation'}]
        raw_bad = json.dumps(bad, ensure_ascii=False, separators=(',', ':'))
        belief.replies = [raw_bad, json.dumps(UPDATE)]
        update, _candidate = ep.manager._request_candidate(
            [{'role': 'user', 'content': 'This event only'}],
            base=ep.manager._current(), operation='update', step=0)
        self.assertEqual(update, UPDATE)
        self.assertEqual(len(belief.requests), 3)  # initialization + two here
        repair_request = belief.requests[-1][-1]['content']
        self.assertIn(raw_bad, repair_request)
        self.assertIn('Normalized patch produced', repair_request)
        self.assertIn('"source_id": "e1"', repair_request)
        self.assertIn('Relation target does not exist', repair_request)
        records = [row for name, row in ep.logger.rows
                   if name == 'belief_candidate_schema_error']
        self.assertEqual(records[-1]['provider_raw_response'], raw_bad)
        self.assertIn('"target_id": "missing-owner"',
                      records[-1]['normalized_patch'])

    def test_filtered_audit_is_unusable_and_keeps_raw_observation(self):
        ep, belief, consistency, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        bad = {'targets': ['e1'], 'issue_type': 'contradiction',
            'problem': 'Unsupported quote', 'evidence_step': 0,
            'evidence_quote': 'NEVER_IN_TOOL', 'evidence': 'NEVER_IN_TOOL',
            'suggestion': 'check again'}
        consistency.replies = [json.dumps({'issues': [bad]})]
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-bad',
                  'result': {'stdout': 'Actual current observation'}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='bad-audit',
            thought='Inspect', action_batch=[{'id': 'tool-bad', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(ep.latest_update_outcome, 'unusable')
        self.assertEqual(ep.manager.belief_update_history[-1]['status'], 'unusable')
        self.assertEqual(ep.accepted_revision, 0)
        self.assertEqual(ep.manager.sentinel.last_audit_result['filtered_count'], 1)
        self.assertEqual(len(belief.requests), 2)  # no repair for invalid issue
        self.assertEqual(len(ep.manager.sentinel.call_progress_model.requests), 0)
        panel = ep.decision_panel(observation='Actual current observation')['panel']
        self.assertIn('may be stale', panel)
        self.assertIn('Actual current observation', ep._pma_observation())
        sys.path.insert(0, str(ROOT.parent / 'GenericAgent-main'))
        from llmcore import NativeClaudeSession, NativeToolClient
        backend = NativeClaudeSession({'apibase': 'https://fixture.invalid',
            'apikey': 'SYNTHETIC-NO-ACCESS', 'model': 'claude-opus-4-8',
            'max_tokens': 64, 'max_retries': 0, 'stream': False})
        captured = []
        class HTTP:
            status_code = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def json(self): return {'content': [{'type': 'text', 'text': 'OK'}],
                                    'usage': {}}
            def close(self): pass
        def post(_url, **kwargs):
            captured.append(kwargs['json'])
            return HTTP()
        with patch('llmcore.requests.post', side_effect=post):
            iterator = NativeToolClient(backend).chat([{'role': 'system',
                'content': 'BASE'}, {'role': 'user', 'content':
                'Actual current observation'}], tools=[{'name': 'inspect'}],
                system_overlay=panel, overlay_request_byte_limit=None)
            list(iterator)
        sent = json.dumps(captured[0])
        self.assertIn('may be stale', sent)
        self.assertIn('Actual current observation', sent)

    def test_empty_and_partial_issues_are_distinct(self):
        ep, _, consistency, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        sentinel = ep.manager.sentinel
        trajectory = [{'step': 0, 'action': None,
            'observation': json.dumps({'tool_results': [{
                'tool_use_id': 'tool-ok', 'result': {'stdout': 'VISIBLE_OK'}}]})}]
        valid = {'targets': ['e1'], 'issue_type': 'contradiction',
            'problem': 'Check result', 'evidence_step': 0,
            'evidence_quote': 'VISIBLE_OK', 'evidence': 'VISIBLE_OK',
            'suggestion': 'retain uncertainty'}
        invalid = dict(valid, evidence_quote='INVISIBLE', evidence='INVISIBLE')
        consistency.replies = [json.dumps({'issues': [invalid, valid]})]
        findings = sentinel.audit_candidate(case_id='shared-test', base_step=0,
            mode='local', belief_before=ep.manager._structured_context(),
            candidate_belief=ep.manager._structured_context(),
            raw_trajectory=trajectory)
        self.assertEqual(len(findings), 1)
        self.assertEqual(sentinel.last_audit_result['outcome'], 'issues')
        self.assertEqual(sentinel.last_audit_result['filtered_count'], 1)
        consistency.replies = ['{"issues": []}']
        self.assertEqual(sentinel.audit_candidate(case_id='shared-test', base_step=0,
            mode='local', belief_before=ep.manager._structured_context(),
            candidate_belief=ep.manager._structured_context(),
            raw_trajectory=trajectory), [])
        self.assertEqual(sentinel.last_audit_result['outcome'], 'clean')

    def test_shared_audit_semantics_and_candidate_diff_are_request_scoped(self):
        ep, _, consistency, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        sentinel = ep.manager.sentinel
        before = deepcopy(ep.manager._structured_context())
        after = deepcopy(before)
        after['world']['states']['new-result'] = {'description': 'new observation'}
        after['epistemic_gaps'] = [{'target': 'new-result',
                                     'description': 'check new result'}]
        consistency.replies = ['{"issues": []}']
        sentinel.audit_candidate(case_id='diff-case', base_step=3, mode='local',
            belief_before=before, candidate_belief=after,
            raw_trajectory=[{'step': 3, 'action': {'name': 'inspect'},
                'observation': 'inspection returned a new result'}])
        request = consistency.requests[-1]
        self.assertIn('state AFTER this action', request[0]['content'])
        self.assertIn('conflate copying with moving or deleting',
                      ' '.join(request[0]['content'].split()))
        payload = json.loads(request[1]['content'].split('\nReturn JSON:', 1)[0])
        self.assertEqual(payload['step'], 3)
        self.assertIsNone(payload['candidate_changes']['states']['new-result']['before'])
        self.assertEqual(payload['candidate_changes']['states']['new-result']['after'],
                         after['world']['states']['new-result'])
        self.assertEqual(payload['candidate_changes']['epistemic_gaps']['before'],
                         before['epistemic_gaps'])
        self.assertEqual(payload['raw_trajectory'][0]['step'], 3)
        self.assertIn('evidence_id', request[1]['content'])
        self.assertNotIn('"evidence_step": 0', request[1]['content'])

    def test_evidence_id_binds_one_visible_fragment_and_derives_step(self):
        ep, _, _, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        sentinel = ep.manager.sentinel
        belief = ep.manager._structured_context()
        trajectory = [{'step': 4, 'action': {'name': 'inspect'},
            'observation': json.dumps({'tool_results': [
                {'tool_use_id': 'first', 'result': {'stdout': 'SAME TEXT alpha'}},
                {'tool_use_id': 'second', 'result': {'stdout': 'SAME TEXT beta'}}]})}]
        seen = []
        def respond(messages):
            request = json.loads(messages[1]['content'].split('\nReturn JSON:', 1)[0])
            fragments = request['raw_trajectory'][0]['citable_sources']
            self.assertEqual(len(fragments), 2)
            self.assertNotEqual(fragments[0]['evidence_id'],
                                fragments[1]['evidence_id'])
            seen.append(fragments)
            issue = {'targets': ['e1'], 'issue_type': 'external',
                'problem': 'Specific candidate change lacks support',
                'evidence_id': fragments[1]['evidence_id'],
                'evidence_quote': 'TEXT beta', 'evidence': 'TEXT beta',
                'suggestion': 'retain the gap'}
            return json.dumps({'issues': [issue]})
        sentinel.call_model = respond
        findings = sentinel.audit_candidate(case_id='ids', base_step=4,
            mode='local', belief_before=belief, candidate_belief=belief,
            raw_trajectory=trajectory)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].issue.evidence_step, 4)
        self.assertEqual(sentinel.last_evidence_bindings[
            seen[0][1]['evidence_id']]['event_id'], 'second')
        sentinel.audit_candidate(case_id='ids', base_step=4, mode='local',
            belief_before=belief, candidate_belief=belief,
            raw_trajectory=trajectory)
        self.assertEqual(seen[0][1]['evidence_id'], seen[1][1]['evidence_id'])

        def rejected(messages):
            request = json.loads(messages[1]['content'].split('\nReturn JSON:', 1)[0])
            fragments = request['raw_trajectory'][0]['citable_sources']
            common = {'targets': ['e1'], 'issue_type': 'external',
                'problem': 'check', 'evidence': 'check', 'suggestion': 'retain'}
            return json.dumps({'issues': [
                dict(common, evidence_id=fragments[0]['evidence_id'],
                     evidence_quote='TEXT beta'),
                dict(common, evidence_id='ev_old_snapshot',
                     evidence_quote='SAME TEXT alpha'),
                dict(common, evidence_id=fragments[1]['evidence_id'],
                     evidence_quote='TEXT beta')]})
        sentinel.call_model = rejected
        findings = sentinel.audit_candidate(case_id='ids', base_step=4,
            mode='local', belief_before=belief, candidate_belief=belief,
            raw_trajectory=trajectory)
        self.assertEqual(len(findings), 1)
        self.assertEqual(sentinel.last_audit_result['filtered_count'], 2)

    def test_strict_audit_rejects_scalar_and_non_list_top_levels(self):
        ep, _, consistency, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        sentinel = ep.manager.sentinel
        for payload in ([], 'text', 7, True, None, {}, {'issues': None},
                        {'issues': 'not a list'}):
            with self.subTest(payload=payload):
                consistency.replies = [json.dumps(payload)]
                with self.assertRaises(RuntimeError):
                    sentinel.audit_candidate(case_id='shared-test', base_step=0,
                        mode='local', belief_before=ep.manager._structured_context(),
                        candidate_belief=ep.manager._structured_context(),
                        raw_trajectory=[])
                self.assertEqual(sentinel.last_audit_result['outcome'], 'unusable')

    def test_strict_audit_filters_bad_issue_shapes_in_both_orders(self):
        ep, _, consistency, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        sentinel = ep.manager.sentinel
        trajectory = [{'step': 0, 'action': None,
            'observation': json.dumps({'tool_results': [{
                'tool_use_id': 'tool-ok', 'result': {'stdout': 'VISIBLE_OK'}}]})}]
        valid = {'targets': ['e1'], 'issue_type': 'contradiction',
            'problem': 'Check result', 'evidence_step': 0,
            'evidence_quote': 'VISIBLE_OK', 'evidence': 'VISIBLE_OK',
            'suggestion': 'retain uncertainty'}
        bad = [None, [], {'targets': ['e1']},
            dict(valid, targets='e1'), dict(valid, targets=[1]),
            dict(valid, evidence_step=True), dict(valid, evidence_step='0'),
            dict(valid, evidence_quote=23)]
        for malformed in bad:
            for order in ((malformed, valid), (valid, malformed)):
                with self.subTest(order=order):
                    consistency.replies = [json.dumps({'issues': order})]
                    findings = sentinel.audit_candidate(case_id='shared-test',
                        base_step=0, mode='local',
                        belief_before=ep.manager._structured_context(),
                        candidate_belief=ep.manager._structured_context(),
                        raw_trajectory=trajectory)
                    self.assertEqual(len(findings), 1)
                    self.assertEqual(sentinel.last_audit_result['outcome'], 'issues')
                    self.assertEqual(sentinel.last_audit_result['filtered_count'], 1)
            consistency.replies = [json.dumps({'issues': [malformed]})]
            self.assertEqual(sentinel.audit_candidate(case_id='shared-test',
                base_step=0, mode='local',
                belief_before=ep.manager._structured_context(),
                candidate_belief=ep.manager._structured_context(),
                raw_trajectory=trajectory), [])
            self.assertEqual(sentinel.last_audit_result['outcome'], 'unusable')

    def test_transport_exception_is_not_converted_to_unusable_response(self):
        ep, _, _, _ = self.make()
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        sentinel = ep.manager.sentinel
        def failed(_messages):
            raise TimeoutError('synthetic transport deadline')
        sentinel.call_model = failed
        with self.assertRaisesRegex(TimeoutError, 'synthetic transport deadline'):
            sentinel.audit_candidate(case_id='shared-test', base_step=0,
                mode='local', belief_before=ep.manager._structured_context(),
                candidate_belief=ep.manager._structured_context(),
                raw_trajectory=[])
        def runtime_failure(_messages):
            raise RuntimeError('synthetic upstream transport failure')
        sentinel.call_model = runtime_failure
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-fail',
                  'result': {'stdout': 'Current raw tool result'}}
        with self.assertRaisesRegex(RuntimeError, 'upstream transport failure'):
            asyncio.run(ep.update(actor_attempt=1, transition_id='transport-fail',
                thought='Inspect', action_batch=[{'id': 'tool-fail',
                    'name': 'inspect', 'arguments': {}, 'order': 0,
                    'status': 'executed'}],
                observation=json.dumps({'tool_results': [source]}),
                source_events=[source]))
        self.assertNotEqual(ep.manager.last_validation_outcome, 'unusable')

    def test_unusable_initialization_has_no_empty_committed_state(self):
        ep, _, consistency, _ = self.make()
        consistency.replies = ['{"issues": [{"invalid": true}]}']
        with self.assertRaisesRegex(RuntimeError, 'initial belief audit unusable'):
            asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        partial = ep.get_result()
        self.assertEqual(partial['initialization_stage'], 'pos_initializing')
        self.assertEqual(partial['pos']['status'], 'unavailable')
        self.assertFalse(ep.started)

    def test_unusable_reaudit_retains_prior_state_not_repaired_candidate(self):
        ep, belief, consistency, _ = self.make()
        issue = {'targets': ['e1'], 'issue_type': 'contradiction',
            'problem': 'Current output conflicts', 'evidence_step': 0,
            'evidence_quote': 'STILL_DIRTY', 'evidence': 'STILL_DIRTY',
            'suggestion': 'keep gap'}
        consistency.replies = ['{"issues": []}', json.dumps({'issues': [issue]}),
                               json.dumps({'issues': [dict(issue,
                                   evidence_quote='NOT_VISIBLE', evidence='NOT_VISIBLE')]})]
        belief.replies.append(json.dumps(UPDATE))
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-r',
                  'result': {'stdout': 'STILL_DIRTY'}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='reaudit-unusable',
            thought='Inspect', action_batch=[{'id': 'tool-r', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(ep.latest_update_outcome, 'unusable')
        self.assertEqual(len(belief.requests), 3)
        self.assertIn('may be stale', ep.decision_panel(
            observation='STILL_DIRTY')['panel'])

    def test_reaudit_json_repair_exhaustion_is_unusable_without_progress(self):
        ep, belief, consistency, _ = self.make()
        issue = {'targets': ['e1'], 'issue_type': 'contradiction',
            'problem': 'Current output conflicts', 'evidence_step': 0,
            'evidence_quote': 'STILL_DIRTY', 'evidence': 'STILL_DIRTY',
            'suggestion': 'keep gap'}
        consistency.replies = ['{"issues": []}', json.dumps({'issues': [issue]}),
                               '{bad json', '{still bad json']
        belief.replies.append(json.dumps(UPDATE))
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-j',
                  'result': {'stdout': 'STILL_DIRTY'}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='reaudit-json',
            thought='Inspect', action_batch=[{'id': 'tool-j', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(ep.latest_update_outcome, 'unusable')
        self.assertEqual(len(belief.requests), 3)  # original update + one repair
        self.assertEqual(len(ep.manager.sentinel.call_progress_model.requests), 0)
        self.assertIn('may be stale', ep.decision_panel(
            observation='STILL_DIRTY')['panel'])

    def test_replacement_patch_applies_once_to_before_and_preserves_changes(self):
        ep, belief, consistency, _ = self.make()
        initial = deepcopy(INITIAL)
        initial['states'] = [{'state_id': 's-old', 'entity_id': 'e1',
            'description': 'Old state'}]
        patch = deepcopy(UPDATE)
        patch['remove_state_ids'] = ['s-old']
        patch['upsert_entities'] = [{'entity_id': 'e2', 'entity_type': 'record',
                                     'name': 'new record'}]
        patch['upsert_states'] = [{'state_id': 's-new', 'entity_id': 'e2',
            'description': 'New state'}]
        belief.replies = [json.dumps(initial), json.dumps(patch), json.dumps(patch)]
        issue = {'targets': ['e1'], 'issue_type': 'contradiction',
            'problem': 'Inspect one local interpretation', 'evidence_step': 0,
            'evidence_quote': 'VISIBLE', 'evidence': 'VISIBLE',
            'suggestion': 'Correct only the local issue'}
        consistency.replies = ['{"issues": []}', json.dumps({'issues': [issue]}),
                               '{"issues": []}']
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        source = {'origin': 'GA_tool_outcome', 'tool_use_id': 'tool-v',
                  'result': {'stdout': 'VISIBLE'}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='replacement-once',
            thought='Inspect', action_batch=[{'id': 'tool-v', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        world = ep.manager._structured_context()['world']
        self.assertNotIn('s-old', world['states'])
        self.assertIn('s-new', world['states'])
        self.assertIn('e2', world['entities'])
        self.assertEqual(world['states']['s-new']['entity_id'], 'e2')
        self.assertEqual(ep.latest_update_outcome, 'accepted')
        repair = json.dumps(belief.requests[2], ensure_ascii=False)
        self.assertIn('s-old', repair)
        self.assertIn('s-new', repair)
        self.assertIn('replacement incremental patch', repair)

    def test_window_outside_source_reaches_phase2_and_repair(self):
        ep, belief, consistency, pma = self.make()
        ep.recent_window = 1
        ep.manager.recent_transition_count = 1
        ep.manager.sentinel.call_progress_model.replies.append(
            '{"progress": 0, "score": 0.0, "affected_record_ids": [], '
            '"reason": "no change"}')
        belief.replies.extend([json.dumps(UPDATE), json.dumps(UPDATE)])
        long_source = ('VISIBLE_HEAD' + 'a' * 4000 +
                       'MIDDLE_NOT_CITABLE' + 'b' * 4000 + 'VISIBLE_TAIL')
        issue = {'targets': ['e1'], 'issue_type': 'contradiction',
                 'problem': 'old selected evidence is relevant',
                 'evidence_step': 0, 'evidence_quote': 'VISIBLE_TAIL',
                 'evidence': 'VISIBLE_TAIL', 'suggestion': 'retain gap'}
        consistency.replies.extend([json.dumps({'issues': [issue]}),
                                    '{"issues": []}'])
        pma.replies.extend([response(), response('<no_intervention/>')])
        asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.', actions=[]))
        pma.replies[0] = response('', [tool('memory_save_knowledge',
            {'content': 'Selected old observed outcome'})])
        first = {'origin': 'GA_tool_outcome', 'tool_use_id': 'old-event',
                 'result': {'stdout': long_source}}
        asyncio.run(ep.update(actor_attempt=1, transition_id='old-transition',
            thought='inspect', action_batch=[{'id': 'old-event', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [first]}), source_events=[first]))
        second = {'origin': 'GA_tool_outcome', 'tool_use_id': 'new-event',
                  'result': {'stdout': 'Current new outcome'}}
        asyncio.run(ep.update(actor_attempt=2, transition_id='new-transition',
            thought='inspect', action_batch=[{'id': 'new-event', 'name': 'inspect',
                'arguments': {}, 'order': 0, 'status': 'executed'}],
            observation=json.dumps({'tool_results': [second]}), source_events=[second]))
        self.assertNotIn('old-event', ep._pma_observation())
        self.assertIn('MIDDLE_NOT_CITABLE', pma.requests[-1]['prompt'])
        self.assertIn('Selected old observed outcome', pma.requests[-1]['prompt'])
        self.assertIn('MIDDLE_NOT_CITABLE', json.dumps(belief.requests[-2]))
        self.assertIn('MIDDLE_NOT_CITABLE', json.dumps(belief.requests[-1]))
        audit = [row for name, row in ep.logger.rows
                 if name == 'shared_audit_source_projection'][-2:]
        self.assertTrue(any(item['step'] == 0 for item in audit[0]['rows']))
        self.assertTrue(any(item['step'] == 0 for item in audit[1]['rows']))
        self.assertEqual(audit[0]['rows'][0]['sources'][0]['field_path'],
                         audit[1]['rows'][0]['sources'][0]['field_path'])
        sentinel = ep.manager.sentinel
        sentinel.shared_selection = ep.frozen_selection
        sentinel.shared_sources = tuple(source for source in ep._selection_sources()
                                        if source.get('origin') == 'tool_result')
        hidden_issue = dict(issue, evidence_quote='MIDDLE_NOT_CITABLE',
                            evidence='MIDDLE_NOT_CITABLE')
        consistency.replies.append(json.dumps({'issues': [hidden_issue]}))
        findings = sentinel.audit_candidate(case_id='case', base_step=1,
            mode='local', belief_before={'world': {'entities': {'e1': {}}}},
            candidate_belief={'world': {'entities': {'e1': {}}}},
            raw_trajectory=ep.manager.raw_trajectory[-1:])
        self.assertEqual(findings, [])
        self.assertNotIn('MIDDLE_NOT_CITABLE', json.dumps(consistency.requests[-1]))

    def test_recovery_survives_silence_and_no_cap(self):
        context = {'goal': {'user_input': 'Original Task'},
            'epistemic_gaps': [], 'achievement_gaps': [],
            'frontier_gap': {'target': 'keep-going'},
            'world': {'entities': {}, 'states': {}, 'relations': {}},
            'recovery': {'instruction': 'R' * 18000},
            'accepted_revision': 2, 'latest_update_outcome': 'accepted'}
        panel = shared_panel(context)
        self.assertIn('R' * 18000, panel['panel'])
        self.assertIsNone(panel['included_advice'])
        self.assertGreater(len(panel['panel']), 16000)

    def test_actual_stateful_task_http_retains_recovery_for_silence_and_rejection(self):
        sys.path.insert(0, str(ROOT.parent / 'GenericAgent-main'))
        from belief.beliefStates import RecoveryDirective
        from llmcore import NativeClaudeSession, NativeToolClient
        for phase2, expected_advice in (('<no_intervention/>', False),
            ('unparseable Phase 2 prose', False),
            ('<context_for_action>Optional synthetic advice</context_for_action>', True)):
            with self.subTest(phase2=phase2):
                ep, *_ = self.make(initial_advice=phase2)
                asyncio.run(ep.reset(task='Clean mug.', observation='Clean mug.',
                                     actions=[]))
                frontier = ep.manager._current().frontier
                ep.manager.active_recovery = RecoveryDirective(
                    recovery_frontier=frontier, trigger_frontier=frontier,
                    gap_dimension='achievement', trapping_pattern='static',
                    started_at_step=0, applies_from_step=0,
                    instruction='KEEP_ACTIVE_RECOVERY_UNABRIDGED')
                panel = ep.decision_panel(observation='Current actual observation')
                backend = NativeClaudeSession({'apibase': 'https://fixture.invalid',
                    'apikey': 'SYNTHETIC-NO-ACCESS', 'model': 'claude-opus-4-8',
                    'max_tokens': 64, 'max_retries': 0, 'stream': False})
                client = NativeToolClient(backend)
                captured = []
                class HTTP:
                    status_code = 200
                    headers = {}
                    def __enter__(self): return self
                    def __exit__(self, *args): return False
                    def json(self): return {'content': [{'type': 'text',
                        'text': 'Synthetic Task response'}], 'usage': {}}
                    def close(self): pass
                def post(_url, **kwargs):
                    captured.append(kwargs['json'])
                    return HTTP()
                with patch('llmcore.requests.post', side_effect=post):
                    iterator = client.chat([{'role': 'system',
                        'content': 'BASE_SYSTEM'}, {'role': 'user',
                        'content': 'Clean mug.'}], tools=[{'name': 'synthetic_tool'}],
                        system_overlay=panel['panel'], overlay_request_byte_limit=None)
                    while True:
                        try:
                            next(iterator)
                        except StopIteration:
                            break
                self.assertEqual(len(captured), 1)
                sent = json.dumps(captured[0])
                self.assertIn('BASE_SYSTEM', sent)
                self.assertIn('KEEP_ACTIVE_RECOVERY_UNABRIDGED', sent)
                self.assertIn('Clean mug.', sent)
                self.assertEqual('Optional synthetic advice' in sent,
                                 expected_advice)


if __name__ == '__main__':
    unittest.main()
