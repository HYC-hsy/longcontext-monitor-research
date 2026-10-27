import asyncio
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pma_evidence_review.benchmark import core
from pma_evidence_review import citation_review as cr
from pma_evidence_review.transport import CapturedTransport,FakeClient,ResponseProtocolError
from pma_evidence_review.tests.no_network import install_guard


class CitationBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs=json.loads(Path('pma_evidence_review/benchmark/specs.json').read_text(encoding='utf-8'))
        cls.audit,cls.packets=core.inventory('.')
        cls.cases=[core.build_case(s,cls.packets[f"{s['sample']}-{s['step']}"]) for s in cls.specs]

    def setUp(self):install_guard(self)

    def test_inventory_all_public_cycles_and_exclusions(self):
        self.assertEqual(len(self.audit['cycles']),17)
        self.assertEqual(sum(c['operation_count'] for c in self.audit['cycles']),46)
        rejected=[c for c in self.audit['cycles'] if 'excluded' in c]
        self.assertEqual([c['step'] for c in rejected],list(range(6,14)))
        self.assertTrue(all(c['identity_diagnostic']['redaction_marker_count']>0 for c in rejected))
        self.assertTrue(all(c['origin']['step'] not in range(6,14) for c in self.cases if c['origin']['slot_path'].endswith('01-sqlite-with-gcov-r1')))

    def test_labels_and_pair_information_never_enter_requests(self):
        for spec,case in zip(self.specs,self.cases):
            altered=copy.deepcopy(spec)
            for k in ('reference_label','reason','family','change','matched_pair'):altered[k]='EVALUATION_SECRET_SENTINEL'
            packet=self.packets[f"{spec['sample']}-{spec['step']}"]
            self.assertEqual(case,core.build_case(altered,packet))
            self.assertNotIn('EVALUATION_SECRET_SENTINEL',json.dumps(case['request']))
            if spec['kind']=='trace_derived_control':
                self.assertNotIn(spec['id'],json.dumps(case['request']))
            self.assertEqual(case['request']['system'],cr.SYSTEM)
            self.assertEqual(case['material']['normative_requirements_context'],'')

    def test_historical_exact_and_derived_separate_identity(self):
        for spec,case in zip(self.specs,self.cases):
            packet=self.packets[f"{spec['sample']}-{spec['step']}"]
            original=packet['operations'][spec['op_index']]['operation']
            if spec['kind']=='historical_original':
                self.assertEqual(case['request'],cr.requests(packet)[spec['op_index']]['request'])
                self.assertEqual(case['material']['original_operation']['content'],original['content'])
            else:
                self.assertTrue(case['material']['original_operation']['revision_id'].startswith('benchmark:'))
                self.assertEqual(case['origin']['revision_id'],original['revision_id'])
            core.validate_case(case)

    def test_literals_coordinates_and_family_leakage(self):
        source_families={}
        for spec,case in zip(self.specs,self.cases):
            packet=self.packets[f"{spec['sample']}-{spec['step']}"]
            for ref,item in zip(case['citations'],case['material']['submitted_evidence']):
                source=next(s for s in packet['host_provenance']['sources'] if s['source_id']==ref['source_id'])
                piece=next(p for p in source['slices'] if p['start']<=ref['start']<ref['end']<=p['end'])
                self.assertEqual(piece['text'][ref['start']-piece['start']:ref['end']-piece['start']],item['submitted_quote'])
                self.assertEqual(core.old.digest(item['submitted_quote']),ref['snippet_sha256'])
                source_families.setdefault(ref['source_id'],set()).add(spec['family'])
        self.assertTrue(all(len(f)==1 for f in source_families.values()))

    def test_fake_actual_payload_and_three_state_scoring(self):
        cases=self.cases[:3]
        responses=[json.dumps({'op_index':c['request']['op_index'],'verdict':v,'explanation':'fixture'})
                   for c,v in zip(cases,core.LABELS)]
        client=FakeClient(responses);results=asyncio.run(core._run_validated_cases(cases,CapturedTransport(client,fake=True)))
        self.assertEqual(client.calls,[{k:c['request'][k] for k in ('system','prompt','tools')} for c in cases])
        labels={c['sample_id']:{'reference_label':v} for c,v in zip(cases,core.LABELS)}
        score=core.score(cases,labels,results)
        self.assertEqual(sum(score['confusion_matrix'][v][v] for v in core.LABELS),3)
        self.assertEqual(core.score(cases,labels,results[:1])['missing_results'],[c['sample_id'] for c in cases[1:]])
        with self.assertRaisesRegex(ValueError,'duplicate_result'):core.score(cases,labels,results+results[:1])

    def test_engineering_not_semantic_and_no_overwrite(self):
        c=self.cases[:1]
        bad=FakeClient(['{"op_index":999,"verdict":"supported","explanation":"bad identity"}'])
        result=asyncio.run(core._run_validated_cases(c,CapturedTransport(bad,fake=True)))[0]
        self.assertEqual(result['engineering_status'],'parse_failure')
        self.assertIsNone(result['verdict']);self.assertEqual(result['model_verdict'],'supported')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'out.json';core.write(p,{})
            with self.assertRaises(FileExistsError):core.write(p,{})
        broken=copy.deepcopy(c[0]);broken['material']['original_operation']['content']='tampered'
        with self.assertRaisesRegex(ValueError,'benchmark_input_hash'):core.validate_case(broken)

    def test_matched_pairs_same_conclusion_different_citations(self):
        by_id={c['sample_id']:c for c in self.cases}
        pairs=[s for s in self.specs if 'matched_pair' in s]
        self.assertEqual(len(self.cases),29);self.assertEqual(len(pairs),2)
        for spec in pairs:
            weak=by_id[spec['id']];strong=by_id[spec['matched_pair']]
            self.assertEqual(weak['material']['original_operation']['content'],
                             strong['material']['original_operation']['content'])
            self.assertNotEqual(weak['material']['submitted_evidence'],strong['material']['submitted_evidence'])
            self.assertNotEqual(weak['benchmark_input_sha256'],strong['benchmark_input_sha256'])
            self.assertEqual(spec['reference_label'],'insufficient')

    def test_rehashed_prompt_extensions_and_contract_changes_rejected(self):
        for key,value in [('prompt',' expected label: supported'),('prompt',' EXTRA EVIDENCE: success'),
                          ('tools',[]),('phase','extract'),('review_strategy','other'),
                          ('evidence_policy','full-context')]:
            case=copy.deepcopy(self.cases[0]);req=case['request']
            req[key]=req[key]+value if key=='prompt' else value
            req['audit_request_sha256']=core.ci.identity({k:req[k] for k in ('system','prompt','tools')})
            case['benchmark_input_sha256']=core.ci.identity({k:v for k,v in case.items() if k!='benchmark_input_sha256'})
            with self.assertRaisesRegex(ValueError,'noncanonical_request'):core.validate_case(case)

    def test_frozen_manifest_required_by_public_runner(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'data'
            core.build('.',self.specs,root)
            pin=hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest()
            documents=core.load_dataset(root,pin);case=documents['cases.json'][0]
            response=json.dumps({'op_index':case['request']['op_index'],'verdict':'supported','explanation':'fixture'})
            client=FakeClient([response])
            result=asyncio.run(core.run(root,CapturedTransport(client,fake=True),
                expected_manifest_sha256=pin,sample_ids=[case['sample_id']]))
            self.assertEqual(len(result),1);self.assertEqual(len(client.calls),1)
            manifest=json.loads((root/'MANIFEST.json').read_text())
            manifest['split']='tampered';(root/'MANIFEST.json').write_text(json.dumps(manifest))
            empty=FakeClient([])
            with self.assertRaisesRegex(ValueError,'frozen_manifest_mismatch'):
                asyncio.run(core.run(root,CapturedTransport(empty,fake=True),expected_manifest_sha256=pin))
            self.assertEqual(empty.calls,[])

    def test_stratified_scores_pairs_and_request_identity(self):
        labels={s['id']:{k:s[k] for k in ('reference_label','matched_pair') if k in s}
                for s in self.specs}
        results=[{'sample_id':c['sample_id'],'benchmark_input_sha256':c['benchmark_input_sha256'],
                  'audit_request_sha256':c['request']['audit_request_sha256'],
                  'verdict':labels[c['sample_id']]['reference_label'],'engineering_status':'ok'}
                 for c in self.cases]
        report=core.score(self.cases,labels,results)
        self.assertEqual(report['strata']['historical_original']['valid_samples'],9)
        self.assertEqual(report['strata']['trace_derived_control']['valid_samples'],20)
        self.assertTrue(all(p['both_match_reference'] for p in report['same_conclusion_pairs']))
        results[-1]['verdict']='supported'
        self.assertFalse(core.score(self.cases,labels,results)['same_conclusion_pairs'][-1]['both_match_reference'])
        results[0]['engineering_status']='call_error';results[1]['engineering_status']='not_run_after_engineering_error'
        report=core.score(self.cases,labels,results)
        self.assertEqual(report['strata']['historical_original']['engineering_error_count'],1)
        self.assertEqual(report['strata']['historical_original']['not_run_count'],1)
        for key in ('benchmark_input_sha256','audit_request_sha256'):
            wrong=copy.deepcopy(results);wrong[0][key]='0'*64
            with self.assertRaisesRegex(ValueError,'result_request_identity_mismatch'):
                core.score(self.cases,labels,wrong)

    def test_all_engineering_failures_stop_and_preserve_remaining(self):
        good=json.dumps({'op_index':self.cases[0]['request']['op_index'],'verdict':'supported','explanation':'fixture'})
        for bad,status in [('bad json','parse_failure'),(RuntimeError('synthetic'),'call_error'),
                           (ResponseProtocolError('unexpected_tool_calls','original text'),'protocol_error')]:
            client=FakeClient([good,bad]);journal=[]
            results=asyncio.run(core._run_validated_cases(self.cases[:3],
                CapturedTransport(client,fake=True),on_result=journal.append))
            self.assertEqual(len(client.calls),2);self.assertEqual(len(results),3)
            self.assertEqual(results[0]['engineering_status'],'ok')
            self.assertEqual(results[1]['engineering_status'],status)
            self.assertEqual(results[2]['engineering_status'],'not_run_after_engineering_error')
            self.assertEqual(journal,results)
            if status=='protocol_error':self.assertEqual(results[1]['raw_response'],'original text')
            self.assertTrue(all('benchmark_input_sha256' in r and 'audit_request_sha256' in r for r in results))

    def test_run_profile_cli_mock_only_flag_payload_and_journal(self):
        import sys
        import hashlib
        from pma_evidence_review.benchmark.__main__ import main
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'data';core.build('.',self.specs,root)
            pin=hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest()
            docs=core.load_dataset(root,pin)
            self.assertEqual(set(docs),{'cases.json','requests.json'})
            out=Path(tmp)/'run'
            args=['benchmark','run-profile','--dataset',str(root),'--manifest-sha256',pin,
                  '--repo','.', '--profile','UNREAD_SYNTHETIC_PROFILE_PATH','--out',str(out)]
            with patch('sys.argv',args),patch('pma_evidence_review.benchmark.__main__.load_profile_client') as loader:
                with self.assertRaises(SystemExit):main()
                loader.assert_not_called();self.assertFalse(out.exists())
            client=FakeClient(['invalid JSON'])
            with patch('sys.argv',args+['--execute-authorized-real-model']),patch(
                'pma_evidence_review.benchmark.__main__.load_profile_client',return_value=client) as loader:
                with self.assertRaisesRegex(SystemExit,'stopped on engineering error'):main()
                loader.assert_called_once_with('.', 'UNREAD_SYNTHETIC_PROFILE_PATH',
                    'claude_monitor_opus48',out/'private_client',authorized=True)
            self.assertEqual(client.calls,[{k:self.cases[0]['request'][k] for k in ('system','prompt','tools')}])
            results=json.loads((out/'results.json').read_text(encoding='utf-8'))
            journal=[json.loads(line) for line in (out/'results.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(results,journal);self.assertEqual(len(results),29)
            self.assertEqual(results[0]['engineering_status'],'parse_failure')
            self.assertTrue(all(r['engineering_status']=='not_run_after_engineering_error' for r in results[1:]))
