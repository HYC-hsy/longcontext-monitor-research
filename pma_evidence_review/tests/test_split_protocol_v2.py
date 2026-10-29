"""Protocol repairs only: fake judgments are not model-effectiveness evidence."""
import asyncio
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace as NS
from pma_evidence_review import claim_split as cs
from pma_evidence_review.tests.test_claim_split import material, split, batch, verification, run
from pma_evidence_review.tests import test_live_gate as host
from pma_evidence_review.tests.no_network import install_guard


class ProtocolV2Tests(unittest.TestCase):
    def setUp(self): install_guard(self)

    def test_gaps_preserved_not_semantically_ignored(self):
        for gap in ('.', ' and ', ' not ', ' if ready ', ' then ', 'Step55:Discovered ',
                    ' < ', ' > ', ' && ', '; Task completed successfully.'):
            text='First'+gap+'Second'
            data={'op_index':0,'claims':[{'claim':c,'original_text':c} for c in ('First','Second')]}
            claims,coverage=cs.parse_split(json.dumps(data),0,text)
            self.assertEqual(coverage['uncovered_original_spans'],[{'start':5,'end':5+len(gap),'text':gap}])
            result,transport=run(material(text),[data,batch([verification(1),verification(2)],False)])
            self.assertEqual(result['verdict'],'insufficient')
            self.assertEqual(transport.calls,2)
            ctx=json.loads(transport.records[1]['request']['prompt'].split('\n',1)[1].split('\nSUBMITTED EVIDENCE ONLY')[0])
            self.assertEqual(ctx['uncovered_original_spans'],coverage['uncovered_original_spans'])
            self.assertIn(text,result['explanation'])

    def test_unique_exact_overrides_wrong_integer_coordinates_only(self):
        value=split('甲😀é\r\nnot done.');value['claims'][0].update(start=99,end=111)
        claims,cov=cs.parse_split(json.dumps(value),0,'甲😀é\r\nnot done.')
        self.assertEqual(claims[0].span.start,0);self.assertEqual(len(cov['offset_corrections']),1)
        for original in ('x < 3 and y > 2','x > 3 and y < 2.'):
            with self.assertRaisesRegex(ValueError,'invalid_span'):
                cs.parse_split(json.dumps(split(original)),0,'x > 3 and y < 2')
        with self.assertRaisesRegex(ValueError,'ambiguous_span'):
            cs.parse_split(json.dumps(split('x')),0,'x x')

    def test_empty_true_explanation_and_host_feedback(self):
        content='Original wording.';claims,_=cs.parse_split(json.dumps(split(content)),0,content)
        raw={'results':[{'claim_index':1,'verdict':'insufficient','evidence_ids':[],
                        'explanation':'No receipt supports this.'}],
             'decomposition_complete':True,'coverage_explanation':''}
        reviews,p=cs.parse_batch(json.dumps(raw),claims,material()['submitted_evidence'],content)
        self.assertEqual(reviews[0]['original_fragment'],content)
        raw['results'][0]['original_fragment']='rewritten, not original'
        self.assertEqual(cs.parse_batch(json.dumps(raw),claims,material()['submitted_evidence'],content)[0],reviews)
        raw['decomposition_complete']=False
        with self.assertRaisesRegex(ValueError,'missing_coverage_explanation'):
            cs.parse_batch(json.dumps(raw),claims,[],content)
        raw['coverage_explanation']='A condition was lost.';raw['coverage_original_fragment']='noncontiguous composite'
        self.assertEqual(cs.parse_batch(json.dumps(raw),claims,[],content)[1]['coverage_original_fragment'],content)

    def isolation_cycle(self, failure="parse", malformed_target=None, invalid_tool=False):
        bank=host.LatestEvidenceGapMemory();key=bank.save_knowledge('old');calls=[]
        async def fake(**kw):
            calls.append(agent.transport_phase)
            if agent.transport_phase=='maintenance':
                first=host.write('bad candidate',key if malformed_target is None else malformed_target)
                if malformed_target is not None:first[1]['memory_id']=malformed_target
                if invalid_tool:first=('unknown_memory_tool',first[1])
                return host.reply([first,host.write('dependent candidate',key),host.write('independent candidate')])
            if agent.transport_phase=='selection':return host.reply(content='<no_intervention/>')
            if kw['prompt'].startswith('CLOSED MATERIAL'):
                m=json.loads(kw['prompt'].split('\n',1)[1]);op=m['original_operation']
                if op['op_index']==0:
                    if failure=='transport':raise RuntimeError('synthetic transport failure')
                    if failure=='cancel':raise asyncio.CancelledError()
                    return host.reply(content='{"claims":[]}')
                value=split(op['content']);value['op_index']=op['op_index']
            else:value=batch([verification()])
            return host.reply(content=json.dumps(value))
        agent=host.CitationGateMemoryAgent(task='synthetic',memory=bank,llm=NS(call=fake),review_strategy=cs.STRATEGY)
        agent.prepare_visible_context('',[{'source_id':'e1','role':'tool_observation','order':1,'field_path':'result',
            'text':host.TEXT,'record_digest':host.sha256(host.TEXT),'record_digest_kind':'event'}])
        result=asyncio.run(agent.process('',1))
        return agent, result, calls, bank, key

    def test_isolation_same_target_blocked_unrelated_continues(self):
        agent,result,calls,bank,key=self.isolation_cycle()
        self.assertEqual([o.success for o in result.operations],[False,False,True])
        rows=agent.last_citation_gate_report['operations']
        self.assertEqual(rows[1]['error_code'],'not_run_failed_target_dependency')
        self.assertEqual(bank.knowledge[0].content,'old')
        self.assertEqual(agent.pending_receipt['operations'][1]['target_memory_id'],key)
        self.assertEqual(calls.count('citation_review'),3)

    def test_global_transport_and_cancel_do_not_continue(self):
        agent,result,calls,bank,key=self.isolation_cycle('transport')
        self.assertFalse(any(o.success for o in result.operations))
        self.assertEqual(calls.count('citation_review'),1)
        self.assertEqual(agent.last_citation_gate_report['operations'][2]['error_code'], 'not_run_after_review_error')
        with self.assertRaises(asyncio.CancelledError):self.isolation_cycle('cancel')

    def test_local_parse_repair_once_no_third_attempt(self):
        from pma_evidence_review.tests.test_claim_split_live import ClaimSplitLiveTests
        replacement={'decision':'replace','content':'First repaired and second repaired.',
                     'evidence':[{'quote':'synthetic file created.'}]}
        agent,result,calls,_=ClaimSplitLiveTests.cycle(self,repairs=[replacement],bad_split=True)
        self.assertFalse(result.operations[0].success)
        self.assertEqual([p for p,_ in calls].count('citation_repair'),1)
        self.assertEqual([p for p,_ in calls].count('citation_review'),2)
        self.assertEqual(len(agent.last_citation_gate_report['operations'][0]['attempts']),2)
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'],'not_committed')

    def test_malformed_targets_do_not_block_valid_operations(self):
        for target in ([], {}, ['k1'], {'id':'k1'}, True, 17):
            with self.subTest(target=target):
                agent,result,calls,bank,key=self.isolation_cycle(malformed_target=target)
                self.assertEqual([o.success for o in result.operations],[False,True,True])
                rows=agent.last_citation_gate_report['operations']
                self.assertEqual(rows[0]['error_code'],'invalid_operation_or_target')
                self.assertFalse(agent.last_citation_gate_report['incomplete'])
                self.assertEqual(calls.count('citation_review'),4)
                self.assertEqual([r['outcome'] for r in agent.pending_receipt['operations']],
                                 ['not_committed','committed','committed'])

    def test_unknown_tool_cannot_block_a_real_target(self):
        agent,result,calls,bank,key=self.isolation_cycle(invalid_tool=True)
        self.assertEqual([o.success for o in result.operations],[False,True,True])
        self.assertEqual(agent.last_citation_gate_report['operations'][0]['error_code'],
                         'invalid_operation_or_target')
        self.assertEqual(calls.count('citation_review'),4)
