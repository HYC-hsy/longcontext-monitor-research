"""Actual LiteLLM/profile conversion under a fake provider; never a network call."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.test_p1_source_agent import STAGE
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tools.run_p1_source_case import profile_client,run_case


def simple_case():
    return {'schema':'p1-maintenance-case-v1','task_id':'neutral-task-1','task':'Original task',
        'initial_bank':{'status':'','knowledge':[{'id':'legacy','content':'Scoped fact','created_at':'fixture'}],
                        'procedural':[],'gaps':[]},
        'entries':[{'event_id':'e1','commands':['{"id":"cmd1","tool_name":"query","args":{"region":"west"}}'],
            'observation':json.dumps({'content':'Actor report','tool_results':[{'tool_use_id':'cmd1','content':'visible receipt'}]})}],
        'prior_presentations':[],'source_windows':[],'entry_sources':[],'step_count':1,
        'observation_dimensions':['WITHHELD_EVALUATION_SENTINEL']}


class P1SourceClientTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_actual_profile_transport_faithful_read_receipts_and_original_write_schema(self):
        import litellm
        from litellm import ModelResponse
        from bank_display_agent import BankDisplayAgent
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);captured=[]
            async def provider(**kw):
                captured.append(deepcopy(kw))
                config=json.loads((root/'run_config.json').read_text())
                self.assertEqual(config['model_parameters']['max_tokens'],2048)
                self.assertEqual(len(config['requests']),len(captured))
                self.assertNotIn('example.invalid',json.dumps(config))
                self.assertNotIn('synthetic-not-a-secret',json.dumps(config))
                if len(captured)==1:
                    calls=[{'id':'provider-read-1','type':'function','function':{
                        'name':'memory_read_source','arguments':json.dumps({'memory_id':'legacy'})}}]
                else:
                    calls=[{'id':'provider-write-1','type':'function','function':{
                        'name':'memory_save_knowledge','arguments':json.dumps({'content':'New scoped observation'})}}]
                return ModelResponse(model='anthropic/claude-opus-4-8', choices=[{
                    'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':'','tool_calls':calls}}],
                    usage={'prompt_tokens':100,'completion_tokens':20,'total_tokens':120})
            profile={'provider':'anthropic','api_mode':'messages','model':'claude-opus-4-8',
                'thinking_type':'adaptive','apibase':'https://example.invalid','apikey':'synthetic-not-a-secret',
                'reasoning_effort':'high','temperature':0.3,'max_tokens':2048,'read_timeout':30}
            llm=profile_client(profile,root/'client')
            with patch('litellm.acompletion',side_effect=provider), \
                 patch.object(BankDisplayAgent,'_call_llm_phase2',side_effect=AssertionError('P2 forbidden')):
                result=asyncio.run(run_case(simple_case(),root,llm))
            self.assertEqual(result['status'],'completed');self.assertEqual(len(captured),2)
            self.assertEqual(result['turns'][0]['usage']['prompt_tokens'],100)
            self.assertNotIn('cost_usd',str(captured[1]['messages']))
            self.assertEqual([len(kw['tools']) for kw in captured],[6,5])
            for kw in captured:
                self.assertEqual(kw['max_tokens'],2048);self.assertEqual(kw['timeout'],30)
                self.assertEqual(kw['thinking'],{'type':'adaptive'})
                self.assertEqual(kw['model'],'anthropic/claude-opus-4-8')
                texts=str(kw['messages'])
                self.assertNotIn('WITHHELD_EVALUATION_SENTINEL',texts)
                self.assertNotIn('synthetic-not-a-secret',texts)
            self.assertIn('provider-read-1',str(captured[1]['messages']))
            self.assertIn('source_unrecorded',str(captured[1]['messages']))
            self.assertIn('legacy',str(captured[1]['messages']))
            journal=(root/'source_archive/maintenance.jsonl').read_text()
            self.assertNotIn('synthetic-not-a-secret',journal)
            self.assertNotIn('example.invalid',journal)
            self.assertEqual(len(json.loads((root/'bank_after.json').read_text())['knowledge']),2)

    def test_long_bank_task_read_delivers_tail_receipt_to_actual_continuation(self):
        from types import SimpleNamespace as NS
        from pma_evidence_review.tests.test_bank_display import reply
        from pma_evidence_review.tools.run_p1_source_case import build_case
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=simple_case();requests=[]
            case['source_windows']=[{'window_id':'origin','model_input':'Long task '+('long bank '*6000),
                'visible_events':[{'event_id':'origin-e','presentation':'new_event',
                    'commands':['run --region west'], 'analysis':'Actor claims success',
                    'observation':json.dumps({'content':'Actor description','tool_results':[
                        {'tool_use_id':'origin-c','content':'SHORT RAW TAIL RECEIPT'}]})}]}]
            case['entry_sources']=[{'memory_id':'legacy','window_id':'origin'}]
            async def fake(**kw):
                requests.append(kw)
                return reply([('memory_read_source',{'memory_id':'legacy'})]) if len(requests)==1 else reply()
            result=asyncio.run(run_case(case,root,NS(call=fake)))
            self.assertEqual(result['status'],'completed')
            self.assertIn('SHORT RAW TAIL RECEIPT',requests[1]['prompt'])
            self.assertIn('run --region west',requests[1]['prompt'])
            self.assertIn('not per-claim evidential support',requests[1]['prompt'])
            receipt=result['turns'][0]['tool_results'][0]['result']
            self.assertTrue(receipt['truncated']);self.assertTrue(receipt['omitted']['full_generation_input'])

    def test_build_case_failure_has_terminal_without_calling_model(self):
        from types import SimpleNamespace as NS
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);case=simple_case();called=[]
            case['entry_sources']=[{'memory_id':'not-live','window_id':'missing'}]
            async def forbidden(**kw):
                called.append(kw)
                raise AssertionError('no model before valid input')
            result=asyncio.run(run_case(case,root,NS(call=forbidden)))
            terminal=json.loads((root/'terminal.json').read_text())
            self.assertEqual(terminal['status'],'engineering_error')
            self.assertEqual(terminal['stage'],'build_case')
            self.assertEqual(terminal['error_type'],'KeyError')
            self.assertEqual(terminal['model_calls_attempted'],0);self.assertEqual(called,[])

    def test_cli_profile_initialization_failure_has_terminal_not_a_hanging_identity(self):
        import sys
        from pma_evidence_review.tools import run_p1_source_case as runner
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'input.json';path.write_text(json.dumps(simple_case()))
            profile=root/'synthetic-profile.json';profile.write_text('{}')
            output=root/'allocated'
            identity=runner.source_identity(strict=False)
            argv=['p1-runner','--case',str(path),'--output',str(output),'--mode','real',
                  '--profile-file',str(profile),'--authorize-real-p1']
            with patch.object(sys,'argv',argv),patch.object(runner,'source_identity',return_value=identity):
                self.assertEqual(runner.main(),1)
            terminal=json.loads((output/'terminal.json').read_text())
            self.assertEqual(terminal,{'status':'engineering_error','stage':'client_initialization',
                'error_type':'KeyError','model_calls_attempted':0})
            self.assertTrue((output/'identity.json').exists())
