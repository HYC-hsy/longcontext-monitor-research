"""Empty task runner and frozen old protocol compatibility, with fake clients."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from pma_evidence_review.tests.test_bank_display import reply, ROOT
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tools.run_p1_requirement_task import run_task, build_task, validate_scenario, source_identity
from pma_evidence_review.tools.run_p1_source_case import build_case,candidate_config
from p1_source_archive import digest,encode
from pma_evidence_review.tools import run_p1_requirement_task as task_runner

CASE = {'schema':'p1-requirement-task-v1','task_id':'gcov-new-task',
    'task':'Build SQLite with gcov in /app/sqlite and make it available through PATH.',
    'cycles':[{'cycle_id':'one','step_count':1,'entries':[{'event_id':'build1',
        'commands':['make'],'observation':'built binary'}]},
        {'cycle_id':'two','step_count':2,'entries':[{'event_id':'path1',
        'commands':['command -v sqlite3'],'observation':'/app/sqlite/sqlite3'}]}]}


class RequirementRunnerTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_new_task_continuous_runner_exports_actual_attributes_and_resumes(self):
        fixed = ['SQLite gcov build in /app/sqlite','SQLite available in PATH']
        responses = [reply([('requirements_initialize',{'requirements':fixed})]),
            reply([('memory_save_knowledge',{'content':'built','requirements':[fixed[0]],'source_ids':['E1']})]),
            reply([('memory_save_knowledge',{'content':'PATH result','requirements':[fixed[1]],'source_ids':['E1']})])]
        requests = []
        async def fake(**kw):
            requests.append(deepcopy(kw))
            return responses.pop(0)
        with tempfile.TemporaryDirectory() as output:
            results = asyncio.run(run_task(CASE,output,NS(call=fake)))
            self.assertEqual([r['status'] for r in results],['completed','completed'])
            self.assertEqual(len(requests),3)
            view = json.loads((Path(output)/'requirement_view.json').read_bytes())
            bank = json.loads((Path(output)/'bank_after.json').read_bytes())
            self.assertEqual(len(view['records']),2)
            self.assertEqual([r['requirements'] for r in view['records']],[[fixed[0]],[fixed[1]]])
            self.assertEqual(set(bank),{'knowledge','procedural','gaps','status'})
            again = asyncio.run(run_task(CASE,output,NS(call=fake),resume=True))
            self.assertTrue(all(r['replayed_completed_cycle'] for r in again))
            self.assertEqual(len(requests),3)
            config = json.loads((Path(output)/'run_config.json').read_bytes())
            self.assertEqual([r['kind'] for r in config['requests']],['requirement_initialization','request','request'])
            self.assertTrue(any(p.endswith('/p1_requirement_agent.py') for p in config['runtime']['source_files']))

    def test_old_nonempty_case_and_bad_scenarios_cannot_be_silently_migrated(self):
        old = json.loads((ROOT/'pma_evidence_review/p1_source_read_delivery/cases/04-counterevidence-to-old-claim.json').read_bytes())
        for data in (old,{**CASE,'initial_bank':{}},{**CASE,'cycles':CASE['cycles']*2},
                     {**CASE,'task':''},{**CASE,'cycles':[{'cycle_id':'x','entries':'wrong'}]}):
            with self.subTest(data=str(data)[:80]), self.assertRaises(ValueError):
                validate_scenario(data)

    def test_old_actual_system_schema_and_frozen_input_digests_unchanged(self):
        expected = json.loads((ROOT/'pma_evidence_review/fixtures/requirement_old_protocol.json').read_bytes())
        case = json.loads((ROOT/'pma_evidence_review/p1_source_read_delivery/cases/04-counterevidence-to-old-claim.json').read_bytes())
        for name,hashes in expected.items():
            with tempfile.TemporaryDirectory() as out, self.subTest(candidate=name):
                agent = build_case(case,out,None,candidate=name)
                raw = agent._public_events(case['entries'])
                prompt = agent._input(case.get('observation') or encode(raw),case['step_count'],raw)[0]
                self.assertEqual(hashes,{'system_sha256':digest(candidate_config(name)[1]),
                    'tools_sha256':digest(encode(agent.get_tools_schema())),'input_sha256':digest(prompt)})

    def test_unknown_extra_initialization_tools_do_not_become_maintenance_tools(self):
        responses = [reply([('requirements_initialize',{'requirements':[]}),
                            ('memory_update_status',{'content':'fake progress'})])]
        async def fake(**kw):
            return responses.pop(0)
        with tempfile.TemporaryDirectory() as output:
            result = asyncio.run(run_task(CASE,output,NS(call=fake)))
            self.assertEqual(result[0]['status'],'initialization_failed')
            view = json.loads((Path(output)/'requirement_view.json').read_bytes())
            self.assertIsNone(view['fixed_requirements'])
            self.assertEqual(view['status'],'')
            self.assertFalse(view['records'])

    def cli(self, base, *, resume=False, real=False):
        args = ['runner','--scenario',str(base/'scenario.json'),'--output',str(base/'output')]
        args += ['--mode','real','--profile-file',str(base/'profile.json'),'--authorize-real-p1'] if real else [
            '--script',str(base/'script.json')]
        if resume:
            args.append('--resume')
        with patch('sys.argv',args), patch.object(task_runner,'source_identity',return_value={'test_identity':True}):
            code = task_runner.main()
        return code,json.loads((base/'output/terminal.json').read_bytes())

    def test_invalid_script_startup_writes_zero_call_terminal_and_can_safely_resume(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base/'scenario.json').write_text(json.dumps(CASE),encoding='utf-8')
            (base/'script.json').write_bytes(b'{bad json')
            code,terminal = self.cli(base)
            self.assertEqual(code,1)
            self.assertEqual((terminal['stage'],terminal['error_type']),('script_loading','JSONDecodeError'))
            self.assertEqual((terminal['model_calls_attempted'],terminal['model_calls_completed']),(0,0))
            self.assertFalse((base/'output/source_archive').exists())
            script = [{'tool_calls':[{'name':'requirements_initialize','arguments':{'requirements':[]}}]}, {}, {}]
            (base/'script.json').write_text(json.dumps(script),encoding='utf-8')
            code,terminal = self.cli(base,resume=True)
            self.assertEqual((code,terminal['status'],terminal['model_calls_attempted']),(0,'completed',3))
            code,terminal = self.cli(base,resume=True)
            self.assertEqual((code,terminal['model_calls_attempted'],terminal['model_calls_completed']),(0,0,0))

    def test_startup_scenario_identity_and_client_errors_have_terminal_stages(self):
        for target in ('scenario','identity','profile','client'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as root:
                base = Path(root)
                (base/'scenario.json').write_text(json.dumps(CASE),encoding='utf-8')
                (base/'script.json').write_text('[]',encoding='utf-8')
                (base/'profile.json').write_text('{broken' if target=='profile' else
                    '{"claude_monitor_opus48":{}}',encoding='utf-8')
                if target=='scenario':
                    (base/'scenario.json').write_text('{broken',encoding='utf-8')
                if target=='identity':
                    args=['runner','--scenario',str(base/'scenario.json'),'--script',str(base/'script.json'),
                          '--output',str(base/'output')]
                    with patch('sys.argv',args), patch.object(task_runner,'source_identity',side_effect=ValueError('fixture')):
                        self.assertEqual(task_runner.main(),1)
                    terminal=json.loads((base/'output/terminal.json').read_bytes())
                else:
                    with patch.object(task_runner,'profile_client',side_effect=ValueError('fake client init failure')) as client:
                        _,terminal=self.cli(base,real=target in ('profile','client'))
                        self.assertEqual(client.call_count,1 if target=='client' else 0)
                expected = {'scenario':'scenario_loading','identity':'runtime_identity',
                            'profile':'client_initialization','client':'client_initialization'}[target]
                self.assertEqual(terminal['stage'],expected)
                self.assertEqual((terminal['model_calls_attempted'],terminal['model_calls_completed']),(0,0))

    def test_runner_exception_after_calls_reports_actual_counts_and_rejects_unsafe_resume(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base/'scenario.json').write_text(json.dumps(CASE),encoding='utf-8')
            (base/'script.json').write_text('[{},{}]',encoding='utf-8')
            async def fail_after_calls(case,output,llm,**kwargs):
                await llm.call(prompt='fake')
                await llm.call(prompt='fake')
                raise OSError('fake output failure')
            with patch.object(task_runner,'run_task',side_effect=fail_after_calls):
                _,terminal=self.cli(base)
            self.assertEqual(terminal['stage'],'task_runner')
            self.assertEqual((terminal['model_calls_attempted'],terminal['model_calls_completed']),(2,2))
            _,terminal=self.cli(base,resume=True)
            self.assertEqual((terminal['status'],terminal['stage']),('engineering_error','resume_preflight'))
            self.assertEqual(terminal['model_calls_attempted'],0)

    def test_failed_client_call_is_attempted_but_not_completed(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            (base/'scenario.json').write_text(json.dumps(CASE),encoding='utf-8')
            (base/'script.json').write_text('[]',encoding='utf-8')
            code,terminal = self.cli(base)
            self.assertEqual((code,terminal['status']),(1,'initialization_failed'))
            self.assertEqual((terminal['model_calls_attempted'],terminal['model_calls_completed']),(1,0))


if __name__=='__main__':
    unittest.main()
