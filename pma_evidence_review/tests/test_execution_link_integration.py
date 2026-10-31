"""Affected production chain: accepted event inventory through batch and repair view."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest

from pma_evidence_review import execution_link
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tests.test_live_gate import LatestEvidenceGapMemory, reply
from pma_evidence_review import claim_split_semantic as v4

D = 'method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013'


class ExecutionLinkIntegrationTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)
        from pathlib import Path
        import sys
        root = Path(__file__).resolve().parents[2] / D.replace('.', '/')
        for path in (root, root / 'vendor/pma_89e5c0d/src',
                     root / 'vendor/pma_89e5c0d/external/harbor/src'):
            if str(path) not in sys.path:
                sys.path.insert(0, str(path))

    def event(self, *, duplicate=False):
        commands = [{'id': 'call-A', 'tool_name': 'code_run',
                     'args': {'script': 'echo alpha-command\necho unselected-private'}}]
        if duplicate:
            commands.extend({'id': f'unused-{i}', 'tool_name': 'code_run',
                             'args': {'script': 'noop'}} for i in range(4))
            commands.append(deepcopy(commands[0]))  # hidden sixth duplicate ID
        return {'event_id': 'accepted-event', 'sequence': 23, 'kind': 'actor_step',
                'actor_attempt': 1, 'step_status': 'normal',
                'response': 'public actor response',
                'commands': [json.dumps(c) for c in commands],
                'observation': json.dumps({'content': 'public actor response',
                    'tool_results': [{'tool_use_id': 'call-A', 'content':
                        json.dumps({'status': 'ok', 'stdout': 'alpha-output'})}]})}

    def test_real_actor_step_captures_complete_ids_without_bodies(self):
        from episode import PMAEpisode
        event = self.event(duplicate=True)
        entries = [{}]
        actor = NS(_research_candidate='pma_gap_evidence_v1', _memory=NS(),
                   _memory_agent=NS(review_strategy=v4.STRATEGY),
                   _trigger=NS(should_trigger=lambda **_: (False, 'not_triggered')),
                   _accumulated_observations=entries)
        def accumulate(**kwargs):
            entries.append(kwargs)
        actor._accumulate_step = accumulate
        episode = NS(agent=actor, started=True, ended=False, last_attempt=1,
                     last_completed_attempt=0)
        asyncio.run(PMAEpisode._actor_step(episode, event))
        inventory = entries[-1]['_execution_inventory']
        self.assertEqual(inventory['commands'].count('call-A'), 2)
        self.assertEqual(inventory['outputs'], ['call-A'])
        self.assertNotIn('unselected-private', json.dumps(inventory))
        self.assertEqual(inventory['digest_kind'], 'accepted_public_envelope')

    def test_real_catalog_to_batch_and_feedback_only_selected_b(self):
        from citation_gate_agent import CitationGateMemoryAgent
        from evidence_gap_context import prepare_context, event_identity
        event = self.event()
        task_event = {'event_id': 'task-event', 'sequence': 0,
                      'kind': 'task_start', 'initial_user_content': 'Synthetic task'}
        seen = []
        async def fake(**kwargs):
            seen.append((agent.transport_phase, kwargs))
            if agent.transport_phase == 'maintenance':
                return reply([('memory_save_knowledge', {'content': 'Observed alpha.',
                    'evidence': [{'quote': 'echo alpha-command'},
                                 {'quote': 'alpha-output'}]})])
            if agent.transport_phase == 'selection':
                return reply(content='<no_intervention/>')
            if len([x for x in seen if x[0] == 'citation_review']) == 1:
                return reply(content=json.dumps(['Observed alpha.']))
            return reply(content=json.dumps([['O', 'supported', 'Command and output are linked.'],
                                             ['C1', 'supported']]))
        agent = CitationGateMemoryAgent(task='Synthetic task', memory=LatestEvidenceGapMemory(),
            llm=NS(call=fake), review_strategy=v4.STRATEGY, repair_limit=0)
        step = {'analysis': event['response'], 'commands': event['commands'],
                'observation': event['observation'], '_evidence_identity': event_identity(event),
                '_execution_inventory': execution_link.inventory_from_accepted_event(event)}
        wrapper = NS(_get_memory_agent_context=lambda: 'visible synthetic trajectory',
            _memory_agent=agent, _task_description='Synthetic task',
            _evidence_task_identity=event_identity(task_event),
            _sliding_window_size=8, _accumulated_observations=[{}, step])
        prepare_context(wrapper)
        result = asyncio.run(agent.process('visible synthetic trajectory', 1))
        self.assertTrue(result.operations[0].success, agent.last_citation_gate_report)
        batches = [x[1] for x in seen if x[0] == 'citation_review']
        self.assertEqual(len(batches), 2)  # one split, one whole batch
        self.assertNotIn('alpha-output', batches[0]['prompt'])
        request = batches[1]
        model = json.loads(request['prompt'].split('\n', 1)[1])
        relation = model['shared_submitted_evidence_B']
        self.assertEqual(relation['executions'], [{'execution': 'X1',
            'command_fragments': ['E1'], 'output_fragments': ['E2']}])
        self.assertEqual([x['link_status'] for x in relation['evidence']],
                         ['same_call_pair', 'same_call_pair'])
        self.assertIn(execution_link.SCOPE_NOTE, request['system'])
        self.assertEqual(request['system'].count(execution_link.SCOPE_NOTE), 1)
        self.assertNotIn('unselected-private', request['prompt'])
        self.assertNotIn('accepted-event', request['prompt'])
        row = agent.last_citation_gate_report['operations'][0]['attempts'][0]
        self.assertEqual(row['repair_feedback']['execution_links'], relation)
        self.assertNotIn('unselected-private', json.dumps(row['repair_feedback']))
        self.assertNotIn('audit_execution_context', row['request'])
        self.assertEqual(row['execution_link']['selected_view'], relation)

    def test_hidden_duplicate_missing_and_window_eviction_remain_unlinked(self):
        from citation_gate_agent import CitationGateMemoryAgent
        from evidence_gap_context import prepare_context, event_identity
        event = self.event(duplicate=True)
        task_event = {'event_id': 'task-event', 'sequence': 0,
                      'kind': 'task_start', 'initial_user_content': 'Synthetic task'}
        agent = CitationGateMemoryAgent(task='Synthetic task', memory=LatestEvidenceGapMemory(),
            llm=NS(call=None), review_strategy=v4.STRATEGY)
        step = {'analysis': event['response'], 'commands': event['commands'],
                'observation': event['observation'], '_evidence_identity': event_identity(event),
                '_execution_inventory': execution_link.inventory_from_accepted_event(event)}
        wrapper = NS(_get_memory_agent_context=lambda: 'visible', _memory_agent=agent,
            _task_description='Synthetic task', _evidence_task_identity=event_identity(task_event),
            _sliding_window_size=8, _accumulated_observations=[{}, step])
        prepare_context(wrapper)
        agent._build_phase1_prompt('visible', 1)
        from gap_evidence_alignment import _validate_catalog
        context = execution_link.context_from_inventory(agent._parts.catalog, _validate_catalog,
                                                         agent._accepted_execution_inventory)
        catalog = agent._parts.catalog
        origins = []
        for visible in catalog.values():
            rec = visible.snapshot.record
            if (rec.field_path in ('commands/0/args/script',
                                   'observation/tool_results/0/content/stdout')
                    and rec.event_id == event['event_id']):
                origins.append({'source_id': rec.source_id, 'role': rec.role,
                                'field_path': rec.field_path, 'event_order': rec.order})
        selected = [{'submitted_quote': 'echo alpha-command' if o['role'] == 'tool_command'
                     else 'alpha-output', 'alternative_origins': [o]} for o in origins]
        view = execution_link.project(selected, context).model_input()
        self.assertEqual(view['executions'], [])  # sixth, unprojected command duplicates ID
        self.assertTrue(all(x['link_status'] == 'unlinked_or_ambiguous'
                            for x in view['evidence']))
        agent._accepted_execution_inventory = {}  # an expired window cannot confer identity
        expired = execution_link.context_from_inventory(catalog, _validate_catalog, {})
        self.assertEqual(execution_link.project(selected, expired).model_input()['executions'], [])

    def test_repair_issue_carries_selected_e_x_not_host_witness(self):
        from citation_gate_agent import CitationGateMemoryAgent
        from evidence_gap_context import prepare_context, event_identity
        event = self.event()
        task_event = {'event_id': 'task-event', 'sequence': 0,
                      'kind': 'task_start', 'initial_user_content': 'Synthetic task'}
        seen = []
        async def fake(**kwargs):
            seen.append((agent.transport_phase, kwargs))
            if agent.transport_phase == 'maintenance':
                return reply([('memory_save_knowledge', {'content': 'Observed alpha.',
                    'evidence': [{'quote': 'echo alpha-command'}, {'quote': 'alpha-output'}]})])
            if agent.transport_phase == 'selection':
                return reply(content='<no_intervention/>')
            if agent.transport_phase == 'citation_repair':
                return reply(content=json.dumps({'decision': 'withdraw'}))
            if len([x for x in seen if x[0] == 'citation_review']) == 1:
                return reply(content=json.dumps(['Observed alpha.']))
            return reply(content=json.dumps([['O', 'insufficient', 'Need a scoped receipt.'],
                                             ['C1', 'insufficient', 'Only a narrow observation.']]))
        agent = CitationGateMemoryAgent(task='Synthetic task', memory=LatestEvidenceGapMemory(),
            llm=NS(call=fake), review_strategy=v4.STRATEGY, repair_limit=1)
        step = {'analysis': event['response'], 'commands': event['commands'],
                'observation': event['observation'], '_evidence_identity': event_identity(event),
                '_execution_inventory': execution_link.inventory_from_accepted_event(event)}
        wrapper = NS(_get_memory_agent_context=lambda: 'visible synthetic trajectory',
            _memory_agent=agent, _task_description='Synthetic task',
            _evidence_task_identity=event_identity(task_event),
            _sliding_window_size=8, _accumulated_observations=[{}, step])
        prepare_context(wrapper)
        result = asyncio.run(agent.process('visible synthetic trajectory', 1))
        self.assertFalse(result.operations[0].success)
        issue = json.loads(next(kw['prompt'] for phase, kw in seen
                                if phase == 'citation_repair'))['review_issue']
        links = issue['repair_feedback']['execution_links']
        self.assertEqual(links['executions'][0], {'execution': 'X1',
            'command_fragments': ['E1'], 'output_fragments': ['E2']})
        self.assertNotIn('unselected-private', json.dumps(issue))
        self.assertNotIn('frozen_sources', json.dumps(issue))


if __name__ == '__main__':
    unittest.main()
