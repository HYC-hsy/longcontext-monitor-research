import copy
import json
import unittest
from audit import prepare, parse_batch, repair_feedback, from_closed_material, ContractError, SYSTEM, system_for, production_result_example

FACTS = ['binary installed', 'binary runnable', 'gcov present', 'PATH session-local only']
REASON = 'Gap resolved: binary installed and runnable, gcov present; PATH modification session-local only.'
BEFORE = {'id':'G2ng7ij2','revision':'rev-old','content':'Tool must be callable in independent process, without temporary PATH export.'}
OP = {'action':'delete','arguments':{'category':'gap','reason':REASON}}
B = [{'quote':s,'role':'observation','event_order':i} for i,s in enumerate(FACTS)]


class AuditTests(unittest.TestCase):
    def batch(self, claims=FACTS, operation=OP, evidence=B, before=BEFORE):
        return prepare('request-1',operation,before,list(claims),evidence,'Independent process required.')

    def review(self, batch, overall='supported', reason='Evidence establishes the exact retirement reason.',
               subverdicts=None):
        subverdicts = subverdicts or ['supported']*(len(batch.labels)-1)
        rows = [['O',overall,reason]] + [[label,v] if v=='supported' else
                [label,v,'Only narrower support; missing scope; an independent receipt could help.']
                for label,v in zip(batch.labels[1:],subverdicts)]
        return parse_batch(batch,json.dumps(rows),completion_request_id='request-1')

    def test_four_true_facts_cannot_override_complete_closure_failure(self):
        batch = self.batch()
        result = self.review(batch,'insufficient',
            'Installed and runnable in one session; independent-process lookup missing; '
            'a fresh-process receipt without export could establish that scope.')
        self.assertFalse(result.publishable)
        self.assertEqual(result.verdict,'insufficient')
        self.assertTrue(all(row[1]=='supported' for row in result.rows[1:]))
        feedback = repair_feedback(batch,result)
        self.assertEqual(feedback['failures'][0]['scope'],'complete_operation')
        self.assertEqual(feedback['failures'][0]['target'],OP)
        self.assertEqual(feedback['before_entry'],BEFORE)
        self.assertIn('independent-process',feedback['failures'][0]['guidance'])

    def test_independent_invocation_sufficient_fixture_accepts(self):
        batch = self.batch(evidence=B+[{'quote':'Fresh process without export finds tool and runs version.'}])
        result = self.review(batch,reason='Independent invocation without export meets the original gap scope.')
        self.assertTrue(result.publishable)

    def test_host_action_workflow_is_focused_and_keeps_output_contract(self):
        for action in ('save','update','delete'):
            operation = {'action':action,'arguments':{'category':'gap','content':'content','reason':'reason'}}
            batch = self.batch(operation=operation, before=BEFORE if action=='delete' else None)
            prompt = system_for(batch)
            self.assertNotIn('{action_guidance}',prompt)
            self.assertIn('1. Read B',prompt)
            self.assertIn('2. Read complete A',prompt)
            self.assertIn('3. Compare B',prompt)
            self.assertIn('4. Give O',prompt)
            self.assertIn('Use exactly supported / contradicted / insufficient',prompt)
            self.assertIn("O's third cell is mandatory",prompt)
            self.assertIn('not a step-by-step reasoning',prompt)
            self.assertEqual('For this gap deletion' in prompt, action=='delete')
            self.assertEqual('For this update' in prompt, action=='update')
            self.assertEqual('For this save' in prompt, action=='save')
            self.assertIn('true subclaims cannot substitute',prompt)

    def test_future_plan_not_required_as_completed(self):
        op = {'action':'save','arguments':{'content':'Compiler exists; plan to run coverage next.'}}
        batch = self.batch(['Compiler exists.','Plan to run coverage next.'],op,
                           [{'quote':'compiler --version succeeded'}],None)
        self.assertTrue(self.review(batch,reason='Compiler premise observed; coverage is only a future plan.').publishable)
        self.assertIn('NOT proof that its planned steps', ' '.join(system_for(batch).split()))

    def test_causal_direction_missing_and_overall_contradiction(self):
        op = {'action':'save','arguments':{'content':'Patch preceded install, therefore patch caused success.'}}
        batch = self.batch(['Patch preceded install.'],op,[{'quote':'patch at t1; install at t2'}],None)
        self.assertEqual(self.review(batch,'insufficient',
            'Order shown; causation missing; a controlled comparison could help.').verdict,'insufficient')
        self.assertEqual(self.review(batch,'contradicted',
            'Receipt shows fresh-process command not found, incompatible with resolved gap.').verdict,'contradicted')

    def test_joint_evidence_and_redundancy_not_resolution_test(self):
        op = {'action':'delete','arguments':{'category':'gap','reason':'Duplicate of retained gap.'}}
        b = [{'quote':'G1 and G2 have the same requirement.'}, {'quote':'G2 retained.'}]
        batch = self.batch(['G2 retained.'],op,b)
        self.assertEqual(len(batch.model_input()['shared_submitted_evidence_B']),2)
        self.assertTrue(self.review(batch,reason='Joint evidence establishes equivalent retained G2; no resolution claimed.').publishable)

    def test_all_required_rows_and_reasons_strict_before_publish(self):
        batch = self.batch(['subfact'])
        good = [['O','supported','Exact retirement scope established.'],['C1','supported']]
        bad = [good[1:], good[:1], good+[good[0]], good+[['C2','supported']],
               [['O','supported'],good[1]], [['O','insufficient',''],good[1]],
               [['O','supported','reason'],['C1','unsupported']],
               [['O','supported','reason'],['C1','insufficient']],
               [['O','supported','reason','extra'],good[1]], {'results':good}]
        for rows in bad:
            with self.subTest(rows=rows):
                result = parse_batch(batch,json.dumps(rows),completion_request_id='request-1')
                self.assertEqual(result.engineering_status,'parse_error')
                self.assertIsNone(result.verdict)
                self.assertFalse(result.publishable)
        result = self.review(batch,subverdicts=['insufficient'])
        self.assertFalse(result.publishable)
        result = parse_batch(batch,json.dumps(list(reversed(good))),completion_request_id='request-1')
        self.assertTrue(result.publishable)
        self.assertEqual(result.rows[0][0],'O')

    def test_wrappers_and_json_boundaries(self):
        batch = self.batch(['x'])
        raw = '[ ["O","supported","Justified at the target scope."], ["C1","supported"] ]'
        for label in ('','json','text'):
            result = parse_batch(batch,f' \n```{label}\n{raw}\n``` \n',completion_request_id='request-1')
            self.assertTrue(result.publishable)
            self.assertTrue(result.normalized)
        for bad in ('reason '+raw,raw+' extra','```json\n'+raw,
                    '```xml\n'+raw+'\n```','```\n'+raw+'\n```\n```\n[]\n```',
                    '```\n'+raw+'\n```\nextra', 'null','NaN',None):
            self.assertEqual(parse_batch(batch,bad,completion_request_id='request-1').engineering_status,'parse_error')

    def test_feedback_control_only_and_frozen_inputs(self):
        op,before,evidence = copy.deepcopy(OP),copy.deepcopy(BEFORE),copy.deepcopy(B)
        batch = self.batch(operation=op,before=before,evidence=evidence)
        frozen = batch.frozen_material
        result = self.review(batch,'insufficient','Local support only; missing fresh invocation; could collect receipt.')
        feedback = repair_feedback(batch,result)
        feedback['original_operation']['arguments']['reason']='pollution'
        op['arguments']['reason']='live mutation'
        before['content']='live mutation'
        self.assertEqual(batch.frozen_material,frozen)
        self.assertNotIn('could collect receipt',batch.frozen_material)
        self.assertNotIn('pollution',batch.frozen_material)
        self.assertFalse(result.publishable)

    def test_host_projection_preserves_quotes_provenance_and_before(self):
        material = {'original_operation':{'op_index':7,'memory_id':'G2ng7ij2',
                    'revision_id':'rev-hash','content_sha256':'host-hash',
                    'action':'delete_gap','content':REASON,'existing_gap':BEFORE['content']},
                    'normative_requirements_context':'Independent process required.',
                    'submitted_evidence':[{'submitted_quote':' exact\ud800 quote\t\n',
                    'alternative_origins':[{'role':'observation','field_path':'stdout',
                    'source_id':'long-native-source-id','event_order':10},
                    {'role':'command','field_path':'code','source_id':'second-id','event_order':11}]}]}
        adapted = from_closed_material('request-1',material,FACTS)
        visible = adapted.batch.model_input()
        self.assertNotIn('rev-hash',adapted.batch.frozen_material)
        self.assertNotIn('long-native-source-id',adapted.batch.frozen_material)
        self.assertIn('long-native-source-id',adapted.host_mapping)
        e = visible['shared_submitted_evidence_B']
        self.assertEqual(len(e),1)
        self.assertEqual(e[0]['quote'],material['submitted_evidence'][0]['submitted_quote'])
        self.assertEqual(len(e[0]['alternative_origins']),2)
        self.assertEqual(visible['target_context_not_evidence']['before_entry']['content'],BEFORE['content'])
        for origin in e[0]['alternative_origins']:
            self.assertIn('event_order',origin)
            self.assertIn('field_path',origin)
        self.assertLess(len(adapted.batch.frozen_material),len(adapted.host_mapping))

    def test_no_new_delete_policy_or_update_preservation_requirement(self):
        with self.assertRaises(ContractError):
            self.batch(operation={'action':'delete','arguments':{'category':'knowledge','reason':'duplicate'}})
        batch = self.batch(['new status'], {'action':'update','arguments':{'content':'new status'}}, before=None)
        self.assertFalse(batch.model_input()['target_context_not_evidence']['before_entry_available'])

    def test_explicit_operation_kind_is_independent_of_before_availability(self):
        for action in ('save_gap', 'save_knowledge', 'save_procedural'):
            material = {'original_operation': {'action':action,'content':'new content'},
                        'submitted_evidence':[], 'normative_requirements_context':''}
            update = from_closed_material('request-1',material,['fact'], operation_kind='update')
            context = update.batch.model_input()['target_context_not_evidence']
            self.assertEqual(context['complete_operation']['action'],'update')
            self.assertFalse(context['before_entry_available'])
            save = from_closed_material('request-1',material,['fact'], operation_kind='save', before=BEFORE)
            context = save.batch.model_input()['target_context_not_evidence']
            self.assertEqual(context['complete_operation']['action'],'save')
            self.assertTrue(context['before_entry_available'])
            for kind in (None, 'delete', True):
                with self.assertRaises(ContractError):
                    from_closed_material('request-1',material,['fact'],operation_kind=kind)
        material['original_operation']['action']='update_status'
        self.assertEqual(from_closed_material('request-1',material,['fact']).batch.model_input()
                         ['target_context_not_evidence']['complete_operation']['action'],'update')
        with self.assertRaises(ContractError):
            from_closed_material('request-1',material,['fact'],operation_kind='save')

    def test_deletion_before_cannot_override_captured_target(self):
        material = {'original_operation':{'action':'delete_gap','content':REASON,
                                         'existing_gap':BEFORE['content']},
                    'submitted_evidence':[], 'normative_requirements_context':''}
        for before in (None, BEFORE):
            result = from_closed_material('request-1',material,FACTS,before=before)
            self.assertEqual(result.batch.model_input()['target_context_not_evidence']
                             ['before_entry']['content'],BEFORE['content'])
        with self.assertRaises(ContractError):
            from_closed_material('request-1',material,FACTS,before={'content':'other gap'})
        with self.assertRaises(ContractError):
            from_closed_material('request-1',material,FACTS,operation_kind='save')
        del material['original_operation']['existing_gap']
        with self.assertRaises(ContractError):
            from_closed_material('request-1',material,FACTS)
        self.assertEqual(from_closed_material('request-1',material,FACTS,before=BEFORE)
                         .batch.model_input()['target_context_not_evidence']['before_entry']['content'],
                         BEFORE['content'])

    def test_production_shape_maps_errors_and_failed_subclaim_explanation(self):
        batch = self.batch(['subfact'])
        result = self.review(batch, subverdicts=['insufficient'])
        mapped = production_result_example(batch,result)
        self.assertEqual(mapped['overall']['verdict'],'supported')
        self.assertEqual(mapped['verdict'],'insufficient')
        self.assertEqual(mapped['model_verdict'],'supported')
        self.assertIn('subclaim: subfact',mapped['explanation'])
        self.assertNotEqual(mapped['explanation'],mapped['overall']['reason'])
        error = parse_batch(batch,'bad',completion_request_id='request-1')
        mapped = production_result_example(batch,error)
        self.assertEqual(mapped['engineering_status'],'parse_failure')
        self.assertEqual(mapped['batch']['engineering_status'],'parse_failure')
        self.assertIsNone(mapped['verdict'])
        self.assertEqual(mapped['reason'],error.error)
        self.assertEqual(mapped['explanation'],error.error)
        self.assertEqual(mapped['claim_reviews'],[])

    def test_required_before_call_association_and_no_caps(self):
        with self.assertRaises(ContractError):
            self.batch(before=None)
        batch = self.batch(['x']*140)
        self.assertEqual(parse_batch(batch,'[]',completion_request_id='other').error,'request_association')
        long_reason='字\ud800\t'*30000
        result = self.review(batch,reason=long_reason)
        self.assertTrue(result.publishable)
        self.assertEqual(result.rows[0][2],long_reason)


if __name__ == '__main__':
    unittest.main()
