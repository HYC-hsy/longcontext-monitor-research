"""Synthetic host-chain tests; no provider, Task, evaluator or archived trajectories."""
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from pma_evidence_review.inputs import D
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.prompt_strategy import ONE_SENTENCE, SUPPORT_SENTENCE
ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/D
for p in (STAGE,STAGE/'vendor/pma_89e5c0d/src',STAGE/'vendor/pma_89e5c0d/external/harbor/src'):
    if str(p) not in sys.path:sys.path.insert(0,str(p))
os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP','True')
from citation_gate_agent import CitationGateMemoryAgent
from latest_evidence_gap_store import LatestEvidenceGapMemory
from gap_evidence import sha256

TEXT='Observed synthetic file created.'
def reply(calls=(),content='original maintenance'):
    return NS(content=content,tool_calls=[NS(function=NS(name=n,arguments=json.dumps(a))) for n,a in calls])
def write(content='candidate',target=None):
    args={'content':content,'evidence':[{'quote':TEXT}]}
    if target:args['memory_id']=target
    return ('memory_save_knowledge',args)

class LiveGateTests(unittest.TestCase):
    def setUp(self):install_guard(self)

    def cycle(self,calls,answers=('supported',),bank=None,side_effect=None,repair_limit=0,repairs=()):
        bank=bank if bank is not None else LatestEvidenceGapMemory()
        inputs=[];answers=iter(answers);repairs=iter(repairs)
        async def fake(**kw):
            inputs.append((agent.transport_phase,kw))
            if agent.transport_phase=='maintenance':return reply(calls)
            if agent.transport_phase=='selection':return reply(content='<no_intervention/>')
            if agent.transport_phase=='citation_repair':
                value=next(repairs)
                if isinstance(value,BaseException):raise value
                return reply(content=json.dumps(value))
            self.assertEqual(agent.transport_phase,'citation_review')
            if side_effect:side_effect(bank)
            answer=next(answers)
            if isinstance(answer,BaseException):raise answer
            index=json.loads(kw['prompt'].split('\n',1)[1].split('\nOUTPUT')[0])['original_operation']['op_index']
            return reply(content=json.dumps({'op_index':index,'verdict':answer,'explanation':'synthetic fixture'}))
        agent=CitationGateMemoryAgent(task='synthetic',memory=bank,llm=NS(call=fake),repair_limit=repair_limit)
        agent.prepare_visible_context('UNQUOTED OBSERVATION',[{'source_id':'e1','role':'tool_observation',
            'order':1,'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
        result=asyncio.run(agent.process('UNQUOTED OBSERVATION',1))
        return agent,result,inputs

    def test_publish_and_closed_payload(self):
        agent,result,inputs=self.cycle([write()])
        self.assertTrue(result.operations[0].success,agent.last_citation_gate_report)
        self.assertEqual([p for p,_ in inputs],['maintenance','citation_review','selection'])
        self.assertEqual(result.raw_response_phase1,'original maintenance')
        self.assertEqual(agent.memory.knowledge[0].content,'candidate')
        req=inputs[1][1]
        self.assertIn(SUPPORT_SENTENCE,req['system'])
        self.assertNotIn('UNQUOTED OBSERVATION',req['prompt'])
        self.assertNotIn('host_provenance',req['prompt'])
        self.assertIn('tool_observation',req['prompt'])
        self.assertIn('candidate',inputs[-1][1]['prompt'])
        self.assertIsNone(agent._review_result)
        with self.assertRaisesRegex(RuntimeError,'already_consumed'):agent._execute_tool_calls(reply())

    def test_opt_in_author_contract_and_baseline_unchanged(self):
        from latest_evidence_gap_agent import latest_phase1_system, LatestEvidenceGapMemoryAgent
        baseline=LatestEvidenceGapMemoryAgent(task='synthetic',memory=LatestEvidenceGapMemory(),llm=NS())
        original_tools=json.loads(json.dumps(baseline.get_tools_schema()))
        original_system=latest_phase1_system()
        for limit in (0,1):
            agent,_,inputs=self.cycle([write()],repair_limit=limit)
            actual=inputs[0][1]
            for forbidden in ('Every valid save becomes the latest content regardless of binding.',
                              'Malformed evidence records binding error while valid content is still committed;',
                              'Use no extra review phase.'):
                self.assertNotIn(forbidden,actual['system'])
                self.assertIn(forbidden,original_system)
            self.assertIn('A later host commit receipt states what actually changed.',actual['system'])
            for tool in actual['tools']:
                function=tool['function']
                if function['name']=='memory_delete':
                    self.assertIn('will not delete',function['description'])
                else:self.assertIn('only the host commit receipt confirms publication',function['description'])
            self.assertEqual(baseline.get_tools_schema(),original_tools)
            self.assertEqual(latest_phase1_system(),original_system)

    def test_invalid_second_context_does_not_reuse_previous_commit_report(self):
        agent,result,_=self.cycle([write()])
        self.assertTrue(result.operations[0].success)
        receipt_id=agent.pending_receipt['receipt_id']
        agent.prepare_visible_context(None,[])
        asyncio.run(agent.process('second observation',2))
        report=agent.last_citation_gate_report
        self.assertEqual(report['operations'],[])
        self.assertEqual(report['error_code'],'maintenance_context_invalid')
        self.assertTrue(report['incomplete'])
        self.assertEqual(report['final_receipt']['receipt_id'],receipt_id)
        self.assertEqual(report['receipt_delivery'],'pending_delivery')
        self.assertEqual(agent.receipt_deliveries,[])

    def test_rejected_receipts_identify_original_targets(self):
        bank=LatestEvidenceGapMemory();a=bank.save_knowledge('same');b=bank.save_knowledge('same')
        agent,_,_=self.cycle([('memory_delete',{'memory_id':a}),('memory_delete',{'memory_id':b}),
                              write('same',a)],('insufficient',),bank)
        items=agent.pending_receipt['operations']
        self.assertEqual([r['target_memory_id'] for r in items],[a,b,a])
        self.assertTrue(all('revision_id' not in r for r in items))

    def test_rejection_retains_old_and_is_not_selected(self):
        bank=LatestEvidenceGapMemory();key=bank.save_knowledge('old')
        a,r,inputs=self.cycle([write('REJECTED SECRET',key)],('insufficient',),bank)
        self.assertFalse(r.operations[0].success)
        self.assertEqual(bank.knowledge[0].content,'old')
        self.assertNotIn('REJECTED SECRET',inputs[-1][1]['prompt'])
        self.assertTrue(a.last_citation_gate_report['operations'][0]['retained_old_value_may_be_stale'])

    def test_preparation_delete_and_status_no_calls(self):
        bank=LatestEvidenceGapMemory();key=bank.save_gap('old gap');bank.update_status('old status')
        calls=[('memory_delete',{'memory_id':key}),('memory_update_status',{'content':'x'*2001}),
               ('memory_save_gap',{'content':'no quote'}),('memory_save_gap',{'content':'bad','evidence':None})]
        a,r,inputs=self.cycle(calls,(),bank)
        self.assertEqual(len(inputs),2)
        self.assertTrue(all(not op.success for op in r.operations))
        self.assertEqual(bank.status,'old status');self.assertEqual(bank.entries[0].id,key)
        self.assertEqual(a.last_citation_gate_report['operations'][0]['error_code'],'not_applicable_delete_protocol')
        self.assertEqual(a.last_citation_gate_report['operations'][1]['error_code'],'status_would_truncate')

    def test_engineering_stops_without_losing_original(self):
        a,r,inputs=self.cycle([write('first'),write('later')],(RuntimeError('offline'),))
        self.assertEqual(r.raw_response_phase1,'original maintenance')
        self.assertEqual(len(r.operations),2)
        self.assertEqual(a.last_citation_gate_report['operations'][1]['error_code'],'not_run_after_review_error')
        self.assertTrue(a.last_citation_gate_report['incomplete'])
        self.assertFalse(a.memory.knowledge)
        self.assertEqual(inputs[-1][0],'selection')

    def test_same_id_sequential_and_stale_generation(self):
        bank=LatestEvidenceGapMemory();key=bank.save_knowledge('old')
        a,r,_=self.cycle([write('first',key),write('second',key)],('supported','supported'),bank)
        self.assertTrue(all(op.success for op in r.operations),a.last_citation_gate_report)
        rows=a.last_citation_gate_report['operations']
        self.assertEqual(rows[1]['input']['previous_revision_id'],rows[0]['input']['operation']['revision_id'])
        self.assertEqual(bank.knowledge[0].content,'second')
        a,r,_=self.cycle([write()],side_effect=lambda b:b.update_status('concurrent'))
        self.assertFalse(r.operations[0].success)
        self.assertFalse(a.memory.knowledge)

    def test_repair_one_attempt_fixed_existing_target(self):
        bank=LatestEvidenceGapMemory();key=bank.save_knowledge('base')
        a,r,inputs=self.cycle([write('initial',key)],('insufficient','supported'),bank,
            repair_limit=1,repairs=[{'decision':'replace','content':'repaired','evidence':[{'quote':TEXT}]}])
        self.assertEqual([p for p,_ in inputs],['maintenance','citation_review','citation_repair','citation_review','selection'])
        self.assertEqual(bank.knowledge[0].id,key);self.assertEqual(bank.knowledge[0].content,'repaired')
        rows=a.last_citation_gate_report['operations'][0]['attempts']
        self.assertNotEqual(rows[0]['candidate']['revision_id'],rows[1]['candidate']['revision_id'])
        self.assertNotIn(rows[0]['candidate']['revision_id'],bank.revisions)
        self.assertEqual(a.pending_receipt['operations'][0]['outcome'],'committed_after_repair')
        self.assertNotIn('review_issue',inputs[3][1]['prompt'])

    def test_new_repair_not_inheriting_failed_draft(self):
        a,r,_=self.cycle([write('initial')],('contradicted','supported'),repair_limit=1,
            repairs=[{'decision':'replace','content':'repaired','evidence':[{'quote':TEXT}]}])
        rows=a.last_citation_gate_report['operations'][0]['attempts']
        self.assertNotEqual(rows[0]['candidate']['memory_id'],rows[1]['candidate']['memory_id'])
        self.assertEqual(len(a.memory.knowledge),1)
        self.assertEqual(rows[1]['input']['previous_revision_id'],None)

    def test_preparation_repair_withdraw_and_second_rejection(self):
        missing=('memory_save_gap',{'content':'no proof'})
        a,r,_=self.cycle([missing],(),repair_limit=1,repairs=[{'decision':'withdraw'}])
        self.assertFalse(r.operations[0].success);self.assertEqual(a.pending_receipt['operations'][0]['outcome'],'withdrawn')
        a,r,inputs=self.cycle([missing],('insufficient',),repair_limit=1,
            repairs=[{'decision':'replace','content':'still insufficient','evidence':[{'quote':TEXT}]}])
        self.assertEqual([p for p,_ in inputs].count('citation_repair'),1)
        self.assertFalse(r.operations[0].success);self.assertFalse(a.memory.entries)
        self.assertEqual(a.last_citation_gate_report['operations'][0]['verdict'],'insufficient')

    def test_repair_error_target_switch_and_engineering_no_repair(self):
        for value in [RuntimeError('fixture'),{'decision':'replace','content':'other','evidence':[],'memory_id':'another'}]:
            a,r,_=self.cycle([write(),write('later')],('insufficient',),repair_limit=1,repairs=[value])
            self.assertTrue(a.last_citation_gate_report['incomplete'])
            self.assertEqual(a.last_citation_gate_report['operations'][1]['error_code'],'not_run_after_review_error')
        a,r,inputs=self.cycle([write()],(RuntimeError('fixture'),),repair_limit=1)
        self.assertNotIn('citation_repair',[p for p,_ in inputs])

    def test_cancel_cleans_unpublished_candidate(self):
        with self.assertRaises(asyncio.CancelledError):
            self.cycle([write()],(asyncio.CancelledError(),))

    def test_receipt_actual_next_maintenance_not_catalog_or_selection(self):
        a,r,_=self.cycle([write('REJECTED BODY')],('insufficient',))
        frozen=a.pending_receipt;inputs=[];catalogs=[]
        async def fake(**kw):
            inputs.append((a.transport_phase,kw))
            if a.transport_phase=='maintenance':
                catalogs.append([v.snapshot.blob.text for v in a._parts.catalog.values()])
                self.assertEqual(sha256(kw['prompt']),a._parts.manifest.request_sha256)
                return reply([])
            return reply(content='<no_intervention/>')
        a.llm.call=fake
        for step in [2,3]:
            a.prepare_visible_context('UNCHANGED',[{'source_id':str(step),'role':'tool_observation','order':step,
                'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
            asyncio.run(a.process('UNCHANGED',step))
        self.assertIn(frozen['receipt_id'],inputs[0][1]['prompt'])
        self.assertIn('REJECTED BODY',inputs[0][1]['prompt'])
        self.assertNotIn(frozen['receipt_id'],inputs[2][1]['prompt'])
        for phase,kw in inputs:
            if phase=='selection':self.assertNotIn('REJECTED BODY',kw['prompt'])
        self.assertTrue(all('REJECTED BODY' not in text and 'synthetic fixture' not in text
                            for texts in catalogs for text in texts))
        self.assertEqual(a.receipt_deliveries[0]['status'],'response_received_consumed')

    def test_receipt_failed_delivery_retained_same_identity(self):
        a,_,_=self.cycle([write()],('insufficient',));rid=a.pending_receipt['receipt_id']
        async def fail(**kw):raise RuntimeError('fixture')
        a.llm.call=fail
        a.prepare_visible_context('again',[{'source_id':'e2','role':'tool_observation','order':2,
            'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
        asyncio.run(a.process('again',2))
        self.assertEqual(a.pending_receipt['receipt_id'],rid)
        self.assertEqual(a.receipt_deliveries[-1]['status'],'delivery_uncertain_retry_same_id')

    def test_actual_episode_worker_audit_and_host_chain_both_modes(self):
        # Test-only packaging compatibility for this Python 3.11 source checkout.
        import importlib.metadata
        import typing_extensions
        original=importlib.metadata.version
        with patch('importlib.metadata.version',side_effect=lambda n:'0.0.0' if n=='harbor' else original(n)),patch('typing.TypedDict',typing_extensions.TypedDict):
            from episode import construct_upstream,PMAEpisode
            from worker_main import install_transport_audit
            from harbor.llms.base import LLMResponse
        for mode in ('gate-only','gate-one-repair'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp)
                wrapper=construct_upstream(root/'upstream',research_candidate='pma_gap_evidence_v1',citation_review_gate=mode)
                agent=wrapper._memory_agent;phases=[];prompts=[]
                async def fake(**kw):
                    phases.append(agent.transport_phase);prompts.append(kw['prompt'])
                    if agent.transport_phase=='maintenance':
                        source=next(v for v in agent._parts.catalog.values() if v.snapshot.record.source_kind=='public')
                        quote=source.snapshot.blob.text
                        return LLMResponse(content='original phase one',tool_calls=reply([
                            ('memory_save_knowledge',{'content':'synthetic requirement','evidence':[{'quote':quote}]})]).tool_calls)
                    if agent.transport_phase=='citation_review':
                        return LLMResponse(content=json.dumps({'op_index':0,'verdict':'supported','explanation':'fixture reviewer output'}))
                    return LLMResponse(content='<no_intervention/>')
                wrapper._memory_llm.call=fake
                episode=PMAEpisode(wrapper,run_id='gate-fake',task_id='synthetic',archive=root/'archive')
                install_transport_audit(wrapper,episode.archive)
                asyncio.run(episode.handle({'kind':'task_start','sequence':1,'event_id':'e1',
                    'run_id':'gate-fake','task_id':'synthetic','initial_user_content':'synthetic requirement'}))
                self.assertEqual(phases,['maintenance','citation_review','selection'])
                self.assertEqual(len(wrapper._memory.knowledge),1)
                payloads=[json.loads(s) for s in (episode.archive/'memory_payload.jsonl').read_text().splitlines()]
                self.assertEqual([p['phase'] for p in payloads],phases)
                self.assertEqual(agent.pending_receipt['operations'][0]['outcome'],'committed')

    def test_config_contract_rejects_silent_baseline(self):
        from citation_gate_config import validate_gate,require_gate_binding,worker_flags
        for mode in ('gate-only','gate-one-repair'):
            self.assertEqual(worker_flags(mode,'pma_gap_evidence_v1'),['--citation-review-gate',mode])
            self.assertEqual(require_gate_binding(mode,{'citation_review_gate':mode},'pma_gap_evidence_v1'),mode)
            with self.assertRaises(ValueError):require_gate_binding(None,{'citation_review_gate':mode},'pma_gap_evidence_v1')
            with self.assertRaises(ValueError):validate_gate(mode,'U')
            with self.assertRaises(ValueError):validate_gate(mode,'pma_gap_evidence_v1','A')
        self.assertEqual(worker_flags(None,'U'),[])

    def test_waiting_audit_keeps_owner_and_nested_process_is_rejected(self):
        bank=LatestEvidenceGapMemory();key=bank.save_knowledge('OLD ACTIVE')
        inputs=[];holder={}
        async def fake(**kw):
            a=holder['agent'];inputs.append(a.transport_phase)
            if a.transport_phase=='maintenance':return reply([write('NOT YET ACTIVE',key)])
            if a.transport_phase=='citation_review':
                self.assertIs(a.memory,bank)
                self.assertEqual(bank.knowledge[0].content,'OLD ACTIVE')
                self.assertEqual([e.content for e in bank.search_knowledge('ACTIVE',top_k=2)],['OLD ACTIVE'])
                with self.assertRaisesRegex(RuntimeError,'serial gate'):await a.process('nested',2)
                self.assertIsNotNone(a._parts)
                return reply(content=json.dumps({'op_index':0,'verdict':'supported','explanation':'fixture'}))
            return reply(content='<no_intervention/>')
        a=CitationGateMemoryAgent(task='test',memory=bank,llm=NS(call=fake));holder['agent']=a
        a.prepare_visible_context('raw',[{'source_id':'x','role':'tool_observation','order':1,
            'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
        result=asyncio.run(a.process('raw',1))
        self.assertTrue(result.operations[0].success)
        self.assertEqual(bank.knowledge[0].content,'NOT YET ACTIVE')

    def test_cancel_retains_all_operation_receipts(self):
        bank=LatestEvidenceGapMemory();holder={}
        async def fake(**kw):
            a=holder['agent']
            if a.transport_phase=='maintenance':return reply([write('first'),write('later')])
            raise asyncio.CancelledError()
        a=CitationGateMemoryAgent(task='test',memory=bank,llm=NS(call=fake));holder['agent']=a
        a.prepare_visible_context('raw',[{'source_id':'x','role':'tool_observation','order':1,
            'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
        with self.assertRaises(asyncio.CancelledError):asyncio.run(a.process('raw',1))
        self.assertFalse(bank.knowledge);self.assertIsNone(a._parts)
        self.assertEqual(len(a.pending_receipt['operations']),2)
        self.assertEqual(a.pending_receipt['operations'][1]['outcome'],'not_run')
        self.assertEqual(a.last_citation_gate_report['raw_response_phase1'],'original maintenance')

    def test_harbor_binding_and_source_validation(self):
        import hashlib
        from citation_gate_config import gate_source_paths,verify_gate_sources
        config={'citation_review_gate':'gate-only','citation_gate_source_sha256':{
            p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in gate_source_paths()}}
        verify_gate_sources(config)
        config['citation_gate_source_sha256'][next(iter(config['citation_gate_source_sha256']))]='0'*64
        with self.assertRaises(ValueError):verify_gate_sources(config)
        # Exercise actual Harbor entry validation before any environment/Task work.
        from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks import verify_live_spec
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);m=p/'manifest.json';auth=p/'authorization.json'
            m.write_text(json.dumps({'config':{'citation_review_gate':'gate-only'}}));auth.write_text('{}')
            spec={'schema':'pma-ga-live-run-v1','mode':'authorized_live','manifest_path':str(m),
                'authorization_path':str(auth),'manifest_sha256':hashlib.sha256(m.read_bytes()).hexdigest(),
                'authorization_sha256':hashlib.sha256(auth.read_bytes()).hexdigest(),
                'research_candidate':'pma_gap_evidence_v1','condition':'B'}
            with self.assertRaisesRegex(ValueError,'gate differs'):verify_live_spec(spec)

    def test_repair_finishes_before_next_same_target_operation(self):
        for repaired_verdict in ('supported','insufficient'):
            bank=LatestEvidenceGapMemory();key=bank.save_knowledge('base')
            a,r,_=self.cycle([write('op0',key),write('op1',key)],
                ('insufficient',repaired_verdict,'supported'),bank,repair_limit=1,
                repairs=[{'decision':'replace','content':'op0 repaired','evidence':[{'quote':TEXT}]}])
            self.assertTrue(r.operations[1].success)
            self.assertEqual(bank.knowledge[0].content,'op1')
            rows=a.last_citation_gate_report['operations']
            previous=rows[1]['input']['previous_revision_id']
            if repaired_verdict=='supported':self.assertEqual(previous,rows[0]['candidate']['revision_id'])
            else:self.assertNotEqual(previous,rows[0]['candidate']['revision_id'])

    def test_receipt_failure_cannot_erase_commit_or_phase1(self):
        with patch('citation_gate_agent.receipt',side_effect=RuntimeError('fixture reporting')):
            a,r,_=self.cycle([write()])
        self.assertTrue(r.operations[0].success)
        self.assertEqual(r.raw_response_phase1,'original maintenance')
        self.assertEqual(len(a.memory.knowledge),1)
        self.assertEqual(a.pending_receipt['operations'][0]['outcome'],'committed')
        self.assertTrue(a.last_citation_gate_report['incomplete'])

    def test_worker_entry_spool_fake_both_modes(self):
        import importlib.metadata,typing_extensions
        original=importlib.metadata.version
        with patch('importlib.metadata.version',side_effect=lambda n:'0.0.0' if n=='harbor' else original(n)),patch('typing.TypedDict',typing_extensions.TypedDict):
            import worker_main
        for mode in ('gate-only','gate-one-repair'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);requests=root/'spool/requests';responses=root/'spool/responses'
                requests.mkdir(parents=True);responses.mkdir()
                for sequence,kind,extra in [(1,'task_start',{'initial_user_content':'Synthetic requirement'}),
                                            (2,'task_end',{'terminal':{'synthetic':True}})]:
                    event={'schema':'pma-ga-events-v1','kind':kind,'sequence':sequence,'event_id':f'e{sequence}',
                        'run_id':'r','task_id':'synthetic',**extra}
                    (requests/f'e{sequence}.json').write_text(json.dumps(event))
                args=NS(private_root=str(root/'private'),requests=str(requests),responses=str(responses),
                    run_id='r',task_id='synthetic',fake_memory=True,deadline_epoch=None,
                    research_candidate='pma_gap_evidence_v1',citation_review_gate=mode)
                with patch.dict(os.environ,{'PMA_MEMORY_PROFILE_FILE':''}):asyncio.run(worker_main.serve(args))
                ready=json.loads((root/'private/worker_ready.json').read_text())
                self.assertEqual(ready['citation_review_gate'],mode)
                payloads=[json.loads(s) for s in (root/'private/archive/memory_payload.jsonl').read_text().splitlines()]
                self.assertEqual([p['phase'] for p in payloads],(['maintenance']+
                    ['citation_review']*3+['selection'] if mode=='gate-only' else
                    ['maintenance','citation_review','citation_review','citation_repair','citation_review','citation_repair','citation_review','selection']))
                cycles=[json.loads(s) for s in (root/'private/archive/gap_cycle.jsonl').read_text().splitlines()]
                self.assertEqual(cycles[0]['citation_gate_report']['repair_limit'],int(mode=='gate-one-repair'))

    def test_r1_empty_then_retry_only_consumes_r1_not_new_r2(self):
        a,_,_=self.cycle([write('first rejected')],('insufficient',));r1=a.pending_receipt['receipt_id']
        stage={'empty':True};seen=[]
        async def fake(**kw):
            seen.append((a.transport_phase,kw['prompt']))
            if a.transport_phase=='maintenance':return reply([] if stage['empty'] else [write('second rejected')],content='')
            if a.transport_phase=='citation_review':return reply(content=json.dumps({'op_index':0,'verdict':'insufficient','explanation':'second fixture'}))
            return reply(content='<no_intervention/>')
        a.llm.call=fake
        for step in (2,3):
            stage['empty']=step==2
            a.prepare_visible_context('again',[{'source_id':str(step),'role':'tool_observation','order':step,
                'field_path':'result','text':TEXT,'record_digest':sha256(TEXT),'record_digest_kind':'event'}])
            asyncio.run(a.process('again',step))
            if step==2:
                self.assertEqual(a.pending_receipt['receipt_id'],r1)
                self.assertEqual(a.receipt_deliveries[-1]['status'],'empty_response_pending')
        r2=a.pending_receipt['receipt_id'];self.assertNotEqual(r1,r2)
        self.assertEqual([x['receipt_id'] for x in a.receipt_deliveries],[r1,r1])
        self.assertEqual(a.receipt_deliveries[-1]['status'],'response_received_consumed')
        self.assertTrue(all(r2 not in prompt for _,prompt in seen))
        self.assertEqual(a.last_citation_gate_report['receipt_delivery'],'pending_delivery')

    def test_repair_manifest_identity_stays_original(self):
        a,_,_=self.cycle([write()],('insufficient','supported'),repair_limit=1,
            repairs=[{'decision':'replace','content':'repair','evidence':[{'quote':TEXT}]}])
        row=a.last_citation_gate_report['operations'][0]
        before,after=row['attempts']
        self.assertEqual(before['input']['maintenance_request_sha256'],after['input']['maintenance_request_sha256'])
        self.assertEqual(before['input']['host_provenance'],after['input']['host_provenance'])
        self.assertNotEqual(row['repair']['request']['audit_request_sha256'],after['input']['maintenance_request_sha256'])

    def test_current_candidate_cannot_become_same_cycle_evidence(self):
        calls=[write('NOVEL_NOT_PREVIOUSLY_VISIBLE'),('memory_save_knowledge',{
            'content':'second','evidence':[{'quote':'NOVEL_NOT_PREVIOUSLY_VISIBLE'}]})]
        a,r,inputs=self.cycle(calls)
        self.assertTrue(r.operations[0].success);self.assertFalse(r.operations[1].success)
        self.assertEqual([p for p,_ in inputs].count('citation_review'),1)
        self.assertIsNone(a.last_citation_gate_report['operations'][1]['verdict'])
        self.assertEqual(len(a.memory.knowledge),1)

    def test_review_protocol_failure_retains_text_and_never_repairs(self):
        from pma_evidence_review.transport import ResponseProtocolError
        a,r,inputs=self.cycle([write()],(ResponseProtocolError('unexpected_tool_calls','retained raw'),),repair_limit=1)
        row=a.last_citation_gate_report['operations'][0]
        self.assertEqual(row['engineering_status'],'protocol_error')
        self.assertEqual(row['raw_response'],'retained raw')
        self.assertNotIn('citation_repair',[p for p,_ in inputs])
        self.assertFalse(r.operations[0].success)

    def test_duplicate_quote_locations_not_semantic_review(self):
        # Use two identical visible occurrences, not two corroborating documents.
        holder={};calls=[]
        async def fake(**kw):
            a=holder['agent'];calls.append(a.transport_phase)
            if a.transport_phase=='maintenance':return reply([write()])
            return reply(content='<no_intervention/>')
        a=CitationGateMemoryAgent(task='test',memory=LatestEvidenceGapMemory(),llm=NS(call=fake));holder['agent']=a
        text=TEXT+' '+TEXT
        a.prepare_visible_context('raw',[{'source_id':'x','role':'tool_observation','order':1,
            'field_path':'result','text':text,'record_digest':sha256(text),'record_digest_kind':'event'}])
        r=asyncio.run(a.process('raw',1))
        self.assertFalse(r.operations[0].success);self.assertNotIn('citation_review',calls)
        self.assertIsNone(a.last_citation_gate_report['operations'][0]['verdict'])

    def test_post_publish_exception_keeps_committed_success(self):
        original=LatestEvidenceGapMemory.publish
        def after_publish(bank,prepared):
            original(bank,prepared)
            raise RuntimeError('fixture after commit')
        with patch.object(LatestEvidenceGapMemory,'publish',new=after_publish):
            a,r,_=self.cycle([write(),write('not run')])
        self.assertTrue(r.operations[0].success)
        self.assertEqual(r.operations[0].content_status,'committed')
        self.assertFalse(r.operations[1].success)
        self.assertEqual(len(a.memory.knowledge),1)
        self.assertEqual(a.pending_receipt['operations'][0]['outcome'],'committed')
