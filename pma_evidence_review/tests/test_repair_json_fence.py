"""Strict existing reviewer envelope handling reused by author repair; offline only."""
import asyncio
import gzip
import hashlib
import json
from pathlib import Path
import unittest
import zipfile

from pma_evidence_review import gate_control
from pma_evidence_review.citation_inputs import strict_json
from pma_evidence_review.review import json_value
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.no_network import install_guard
from pma_evidence_review.tests import test_live_gate as host

ROOT=Path(__file__).resolve().parents[2]
ARCHIVE='pma_evidence_review/diagnostic_packages/PMA_CITATION_GATE_FOUR_REAL_TASKS_COMPLETE_V2_20261028.zip'
ARCHIVE_SHA='4e14d6241dc7588ae5817fce40a23da233b75a2d41bc32039b5c84eb7b468b8e'
BASE='a250c8aedf61a85f91ec72532ab6e8c02df96617'


def fenced(value):return '```json\n'+json.dumps(value,ensure_ascii=False)+'\n```'


def parse_repair(raw,index=0):
    transport=CapturedTransport(FakeClient([raw]),fake=True)
    result=asyncio.run(gate_control.repair(transport,'Synthetic replay context',
        'memory_save_knowledge',{'content':'synthetic original','evidence':[]},
        {'preparation':'synthetic'},index))
    assert transport.calls==1 and result['raw_response']==raw
    return result


def replay_archive():
    """Use only ZIP members in memory; emit identities/results, never raw content."""
    archive=ROOT/ARCHIVE;data=archive.read_bytes()
    assert len(data)==16938429 and hashlib.sha256(data).hexdigest()==ARCHIVE_SHA
    results=[]
    with zipfile.ZipFile(archive) as z:
        for slot,count in (('02-sqlite-gate-one-repair',12),('04-html-gate-one-repair',2)):
            prefix='real/'+slot+'/gate/'
            members={name:z.read(prefix+name+'.jsonl.gz') for name in ('gate_cycles','responses')}
            rows={name:[json.loads(line) for line in gzip.decompress(raw).splitlines()]
                  for name,raw in members.items()}
            selected=0
            for cycle in rows['gate_cycles']:
                for op in cycle['value']['operations']:
                    if op.get('error_code')!='repair_parse_failure':continue
                    saved=op['repair'];request_sha=saved['request']['audit_request_sha256']
                    matches=[r for r in rows['responses'] if r['value']['phase']=='citation_repair'
                             and r['value']['audit_request_sha256']==request_sha]
                    assert len(matches)==1
                    response=matches[0];raw=response['value']['response']
                    assert raw==saved['raw_response'] and raw.startswith('```json\n') and raw.endswith('\n```')
                    try:strict_json(raw)
                    except ValueError:pass
                    else:raise AssertionError('archive no longer reproduces bare-JSON failure')
                    result=parse_repair(raw,op['index'])
                    assert result['engineering_status']=='ok'
                    assert result['replacement']==json_value(raw)
                    results.append({'slot':slot,'op_index':op['index'],
                        'cycle_member':prefix+'gate_cycles.jsonl.gz','cycle_source_line':cycle['source_line'],
                        'cycle_source_line_sha256_as_archived':cycle['source_line_sha256'],
                        'response_member':prefix+'responses.jsonl.gz','response_source_line':response['source_line'],
                        'response_source_line_sha256_as_archived':response['source_line_sha256'],
                        'response_text_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                        'response_member_sha256':hashlib.sha256(members['responses']).hexdigest(),
                        'audit_request_sha256_as_archived':request_sha,
                        'historical_status':'repair_parse_failure','offline_status':'schema_valid_candidate',
                        'semantic_review_performed':False,'published_to_memory':False})
                    selected+=1
            assert selected==count,(slot,selected)
    return {'source_commit':BASE,'archive':ARCHIVE,'archive_sha256':ARCHIVE_SHA,'archive_bytes':len(data),
            'scope':'Redacted public projection; source_line hashes retained as archived, not asserted to hash the projected value.',
            'results':results}


class RepairFenceTests(unittest.TestCase):
    def setUp(self):install_guard(self)

    def test_bare_fenced_and_withdraw_keep_raw(self):
        for value in ({'decision':'withdraw'}, {'decision':'replace','content':'new',
                                               'evidence':[{'quote':'literal','source':'s1'}]}):
            for raw in (json.dumps(value),fenced(value),' \n'+fenced(value)+'\n '):
                with self.subTest(raw=raw):
                    self.assertEqual(parse_repair(raw)['replacement'],value)
                    self.assertEqual(json_value(raw),value)
        with self.assertRaises(ValueError):strict_json(fenced({'decision':'withdraw'}))

    def test_fence_does_not_change_request_payload_or_raw_output(self):
        value={'decision':'replace','content':'new','evidence':[{'quote':'literal'}]}
        bare=parse_repair(json.dumps(value));wrapped=parse_repair(fenced(value))
        self.assertEqual(bare['request'],wrapped['request'])
        self.assertEqual(bare['replacement'],wrapped['replacement'])
        self.assertEqual(wrapped['raw_response'],fenced(value))

    def test_envelope_and_schema_rejections(self):
        valid='{"decision":"withdraw"}'
        invalid=['prefix\n'+fenced({'decision':'withdraw'}),fenced({'decision':'withdraw'})+'\nsuffix',
                 '```json\n'+valid,valid+'\n```',valid+valid,
                 fenced({'decision':'withdraw'})+'\n'+fenced({'decision':'withdraw'}),
                 '```\n'+valid+'\n```','```JSON\n'+valid+'\n```','```json\r\n'+valid+'\r\n```',
                 '{"decision":"replace","decision":"withdraw"}',
                 '```json\n{"decision":"withdraw","decision":"withdraw"}\n```',
                 '{"decision":"withdraw","extra":1}',
                 '{"decision":"replace","content":5,"evidence":[]}',
                 '{"decision":"replace","content":"x","evidence":{}}',
                 '{"decision":"replace","content":"x","evidence":[{"quote":5}]}',
                 '{"decision":"replace","content":"x","evidence":[{"quote":"a","quote":"b"}]}',
                 '{"decision":"replace","content":"x","evidence":[{"quote":"x","source":5}]}',
                 '{"decision":"replace","content":"x","evidence":[],"memory_id":"other"}',
                 '[]','null','']
        for raw in invalid:
            with self.subTest(raw=raw):
                result=parse_repair(raw)
                self.assertEqual(result['engineering_status'],'parse_failure')
                self.assertNotIn('replacement',result)

    def test_fenced_repair_runs_second_audit_and_never_third(self):
        for verdict in ('supported','insufficient','contradicted'):
            bank=host.LatestEvidenceGapMemory();target=bank.save_knowledge('old')
            value={'decision':'replace','content':'repaired','evidence':[{'quote':host.TEXT}]}
            agent,result,requests=host.LiveGateTests.cycle(self,[host.write('initial',target)],
                ('insufficient',verdict),bank,repair_limit=1,repairs=[fenced(value)],raw_repairs=True)
            self.assertEqual([p for p,_ in requests],['maintenance','citation_review','citation_repair','citation_review','selection'])
            self.assertEqual(bank.knowledge[0].id,target)
            self.assertEqual(bank.knowledge[0].content,'repaired' if verdict=='supported' else 'old')
            self.assertEqual(result.operations[0].success,verdict=='supported')
            receipt=agent.pending_receipt['operations'][0]
            self.assertEqual(receipt['target_memory_id'],target)
            self.assertEqual(receipt['outcome'],'committed_after_repair' if verdict=='supported' else 'not_committed')
            row=agent.last_citation_gate_report['operations'][0]
            self.assertEqual(len(row['attempts']),2)
            self.assertEqual(row['repair']['raw_response'],fenced(value))

    def test_bad_repair_quotes_do_not_bypass_preparation(self):
        bank=host.LatestEvidenceGapMemory();target=bank.save_knowledge('old')
        value={'decision':'replace','content':'repaired','evidence':[{'quote':'not visible'}]}
        agent,result,requests=host.LiveGateTests.cycle(self,[host.write('initial',target)],
            ('insufficient',),bank,repair_limit=1,repairs=[fenced(value)],raw_repairs=True)
        self.assertFalse(result.operations[0].success);self.assertEqual(bank.knowledge[0].content,'old')
        self.assertEqual([p for p,_ in requests].count('citation_review'),1)
        self.assertEqual([p for p,_ in requests].count('citation_repair'),1)
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'],'not_committed')

    def test_fenced_withdraw_and_invalid_target_keep_stop_contract(self):
        agent,result,requests=host.LiveGateTests.cycle(self,[host.write()],('insufficient',),
            repair_limit=1,repairs=[fenced({'decision':'withdraw'})],raw_repairs=True)
        self.assertFalse(result.operations[0].success)
        self.assertEqual(agent.pending_receipt['operations'][0]['outcome'],'withdrawn')
        self.assertEqual([p for p,_ in requests].count('citation_review'),1)
        value={'decision':'replace','content':'x','evidence':[],'memory_id':'another'}
        agent,result,requests=host.LiveGateTests.cycle(self,[host.write(),host.write('later')],
            ('insufficient',),repair_limit=1,repairs=[fenced(value)],raw_repairs=True)
        self.assertFalse(any(op.success for op in result.operations))
        rows=agent.last_citation_gate_report['operations']
        self.assertEqual(rows[0]['error_code'],'repair_parse_failure')
        self.assertEqual(rows[1]['error_code'],'not_run_after_review_error')
        self.assertEqual([p for p,_ in requests].count('citation_repair'),1)

    def test_fourteen_archived_failures_become_schema_candidates_only(self):
        self.assertEqual(len(replay_archive()['results']),14)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Offline redacted-response schema replay; no semantic review or publication.')
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    guard=unittest.TestCase();install_guard(guard)
    try:
        result=replay_archive()
        with args.out.open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print('14 archived responses replayed as schema candidates only; raw history unchanged.')
    finally:guard.doCleanups()
