"""Real client adapter with fake provider, source identity and frozen cases."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.test_bank_display import ROOT, reply
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tests.test_p1_source_client import simple_case
from pma_evidence_review.tools.run_p1_source_case import source_identity, run_case, profile_client
from p1_linked_agent import SYSTEM


class LinkedRunnerTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_all_six_frozen_cases_scripted_noop_only_one_p1_call(self):
        folder=ROOT/'pma_evidence_review/p1_source_read_delivery/cases'
        index=json.loads((folder/'INDEX.json').read_text())
        for row in index['cases']:
            with self.subTest(case=row['file']),tempfile.TemporaryDirectory() as tmp:
                raw=(folder/row['file']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
                case=json.loads(raw);requests=[]
                async def fake(**kwargs):
                    requests.append(deepcopy(kwargs));return reply()
                result=asyncio.run(run_case(case,tmp,NS(call=fake),candidate='source-links-v1'))
                self.assertEqual(result['status'],'completed',result)
                self.assertEqual(len(requests),1)
                self.assertEqual(requests[0]['system'],SYSTEM)
                self.assertEqual(result['operations'],[])
                saved=json.loads((Path(tmp)/'bank_after.json').read_text())
                self.assertEqual(saved,case['initial_bank'])
                config=json.loads((Path(tmp)/'run_config.json').read_text())
                self.assertEqual((config['read_limit'],config['continuation_limit']),(4,2))
                self.assertFalse(config['native_messages_tool_roundtrip'])

    def test_real_profile_adapter_three_logical_turns_under_fake_provider(self):
        from litellm import ModelResponse
        case=simple_case();case['entries'][0]['observation']=' 结果🙂\n\t'*8000
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);captured=[]
            async def provider(**kwargs):
                captured.append(deepcopy(kwargs))
                if len(captured)==1:
                    name,args='memory_read_source',{'memory_id':'E1'}
                elif len(captured)==2:
                    rows=[json.loads(line) for line in (root/'source_archive/maintenance.jsonl').read_text().splitlines()]
                    prior=[r for r in rows if r['kind']=='response_and_receipts'][-1]
                    page=prior['tool_results'][0]['result']
                    name,args='memory_read_source',{'memory_id':'E1','cursor':page['next_cursor']}
                    self.assertIn('next_cursor',str(kwargs['messages']))
                else:
                    name,args='memory_save_knowledge',{'content':'Scoped summary','source_ids':['E1','TASK']}
                return ModelResponse(model='anthropic/claude-opus-4-8',choices=[{'index':0,'finish_reason':'tool_calls',
                    'message':{'role':'assistant','content':'','tool_calls':[{'id':f'provider-{len(captured)}','type':'function',
                    'function':{'name':name,'arguments':json.dumps(args)}}]}}],
                    usage={'prompt_tokens':100,'completion_tokens':10,'total_tokens':110})
            profile={'provider':'anthropic','api_mode':'messages','model':'claude-opus-4-8',
                'thinking_type':'adaptive','apibase':'https://example.invalid','apikey':'synthetic-not-a-secret',
                'reasoning_effort':'high','temperature':0.3,'max_tokens':2048,'read_timeout':30}
            llm=profile_client(profile,root/'client')
            with patch('litellm.acompletion',side_effect=provider):
                result=asyncio.run(run_case(case,root,llm,candidate='source-links-v1'))
            self.assertEqual(result['status'],'completed')
            self.assertEqual(len(captured),3)
            self.assertEqual([len(r['tools']) for r in captured],[6,6,5])
            self.assertEqual(result['reads_used'],2)
            config=json.loads((root/'run_config.json').read_text())
            self.assertEqual(len(config['requests']),3)
            self.assertEqual(config['model_parameters']['model'],'anthropic/claude-opus-4-8')
            self.assertNotIn('synthetic-not-a-secret',(root/'source_archive/maintenance.jsonl').read_text())
            self.assertNotIn('example.invalid',json.dumps(config))
            bindings=json.loads((root/'source_archive/source_links.json').read_text())['data']['refs']
            latest=list(bindings.values())[-1]
            self.assertEqual([s['source_id'] for s in latest['sources']],['TASK','event_1'])

    def test_actual_identity_inventory_rejects_missing_and_changed_new_sources(self):
        identity=source_identity(strict=False,candidate='source-links-v1')
        paths=identity['source_files']
        self.assertEqual(len(paths),61)
        added=[p for p in paths if p.endswith(('/p1_source_links.py','/p1_linked_agent.py'))]
        self.assertEqual(len(added),2)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in paths:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/name).read_bytes())
            subprocess.run(['git','init','-q',str(root)],check=True)
            subprocess.run(['git','add','.'],cwd=root,check=True)
            subprocess.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                'commit','-qm','identity fixture'],cwd=root,check=True)
            self.assertEqual(source_identity(root=root,candidate='source-links-v1')['source_files'],paths)
            for name in added:
                original=(root/name).read_bytes()
                (root/name).unlink()
                with self.assertRaises(RuntimeError):
                    source_identity(root=root,candidate='source-links-v1')
                (root/name).write_bytes(original+b'\n')
                with self.assertRaises(RuntimeError):
                    source_identity(root=root,candidate='source-links-v1')
                (root/name).write_bytes(original)
