"""Synthetic domain-neutral fixtures, not historical logs or model verdicts."""
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from dataclasses import make_dataclass
from execution_projection import (Context, encoded, digest_text, project,
    context_from_catalog, replace_evidence_view, ProjectionError)


def fixture(command_ids=('a',), result_ids=('a',), event='one'):
    sources, selected = {}, []
    for side, ids in (('command',command_ids),('output',result_ids)):
        for i, call in enumerate(ids):
            path = f'commands/{i}' if side=='command' else f'observation/tool_results/{i}/content'
            role = 'tool_command' if side=='command' else 'tool_observation'
            body = 'echo alpha\necho unselected-neighbor' if side=='command' else 'alpha\n'
            leaf = 'args/script' if side=='command' else 'stdout'
            parent = json.dumps({'id':call,'args':{'script':body}}) if side=='command' else json.dumps({'status':'ok','stdout':body})
            root_sid = add(sources,event,path,role,parent,call)
            sid = add(sources,event,path+'/'+leaf,role,body,call,root_sid)
            quote = 'echo alpha' if side=='command' else body
            selected.append({'submitted_quote':quote,'alternative_origins':[
                {'source_id':sid,'role':role,'field_path':path+'/'+leaf,'event_order':23}]})
    return selected,sources


def add(sources,event,path,role,text,call,parent=None):
    sid=json.dumps(['bank','public',event,path],separators=(',',':'))
    sources[sid]={'record':{'source_id':sid,'namespace':'bank','source_kind':'public',
        'event_id':event,'order':23,'field_path':path,'role':role,'tool_call_id':call,
        'text_sha256':digest_text(text),'record_digest':'synthetic-digest-'+event,
        'record_digest_kind':'accepted_public_envelope','parent_wrapper_source_id':parent},'text':text}
    return sid


def run(rows,sources):
    inventory = {}
    for source in sources.values():
        rec = source['record']
        item = inventory.setdefault(rec['event_id'], {'digest':rec['record_digest'],
                'digest_kind':'accepted_public_envelope',
                'order':rec['order'],'commands':[],'outputs':[]})
        if rec['parent_wrapper_source_id'] is None:
            item['commands' if rec['role']=='tool_command' else 'outputs'].append(rec['tool_call_id'])
    return project(rows,Context(encoded(sources),encoded(inventory)))


class ProjectionTests(unittest.TestCase):
    def test_unique_call_reorders_by_id_and_only_selected_text_reaches_model(self):
        rows,sources=fixture(('a','b'),('b','a'))
        result=run(rows,sources); view=result.model_input()
        self.assertEqual(view['executions'][0]['output_fragments'],['E4'])
        self.assertEqual(view['executions'][1]['output_fragments'],['E3'])
        self.assertEqual([q['quote'] for q in view['evidence']], [r['submitted_quote'] for r in rows])
        self.assertNotIn('unselected-neighbor',result.model_json)
        self.assertNotIn('synthetic-digest',result.model_json)
        self.assertNotIn('success',view['executions'][0])
        # Same array index/event, different IDs: retain their distinct call identity.
        separate=run([rows[0],rows[2]],sources).model_input()
        self.assertEqual(separate['executions'],[
            {'execution':'X1','command_fragments':['E1'],'output_fragments':[]},
            {'execution':'X2','command_fragments':[],'output_fragments':['E2']}])
        self.assertTrue(all(q['link_status']=='verified_call_single_side' for q in separate['evidence']))
        self.assertEqual([q['quote'] for q in separate['evidence']],
                         [rows[0]['submitted_quote'],rows[2]['submitted_quote']])

    def test_same_digest_with_other_digest_kind_stays_unlinked(self):
        rows,sources=fixture()
        original={sid:source['record']['record_digest'] for sid,source in sources.items()}
        for source in sources.values():
            source['record']['record_digest_kind']='different_digest_semantics'
        view=run(rows,sources).model_input()
        self.assertEqual(view['executions'],[])
        self.assertTrue(all(q['link_status']=='unlinked_or_ambiguous' for q in view['evidence']))
        self.assertEqual(original,{sid:s['record']['record_digest'] for sid,s in sources.items()})
        rows,sources=fixture()
        output=rows[1]['alternative_origins'][0]['source_id']
        root=sources[output]['record']['parent_wrapper_source_id']
        sources[root]['record']['record_digest_kind']='different_digest_semantics'
        self.assertEqual(run(rows,sources).model_input()['executions'],[])

    def test_missing_duplicate_ids_and_half_selected_not_confirmed(self):
        for commands,results in (((None,),('a',)),(('a',),(None,)),
                                 (('a','a'),('a',)),(('a',),('a','a')), (('a',),())):
            rows,sources=fixture(commands,results)
            with self.subTest(commands=commands,results=results):
                view=run(rows,sources).model_input()
                self.assertEqual(view['executions'],[])
                self.assertEqual(len(view['evidence']),len(rows))
        rows,sources=fixture()
        single=run(rows[:1],sources).model_input()
        self.assertEqual(single['executions'],[{'execution':'X1','command_fragments':['E1'],'output_fragments':[]}])
        self.assertEqual(single['evidence'][0]['link_status'],'verified_call_single_side')
        child=rows[0]['alternative_origins'][0]['source_id']
        sources.pop(sources[child]['record']['parent_wrapper_source_id'])
        self.assertEqual(run(rows,sources).model_input()['executions'],[])

    def test_cross_event_same_order_or_id_and_alternative_ambiguity(self):
        a,sa=fixture(event='one'); b,sb=fixture(event='two'); sources={**sa,**sb}
        known=run([a[0],b[1]],sources).model_input()
        self.assertEqual(known['executions'],[
            {'execution':'X1','command_fragments':['E1'],'output_fragments':[]},
            {'execution':'X2','command_fragments':[],'output_fragments':['E2']}])
        self.assertTrue(all(q['link_status']=='verified_call_single_side' for q in known['evidence']))
        mixed=deepcopy(a[1]);mixed['alternative_origins']+=b[1]['alternative_origins']
        view=run([a[0],mixed],sources).model_input()
        self.assertEqual(view['executions'],[
            {'execution':'X1','command_fragments':['E1'],'output_fragments':[]}])
        self.assertEqual(view['evidence'][1]['link_status'],'unlinked_or_ambiguous')
        self.assertEqual(len(view['evidence'][1]['alternative_origins']),2)
        self.assertEqual(len(view['evidence']),2)

    def test_leafs_deduplicate_root_not_result_count(self):
        rows,sources=fixture()
        old=rows[1]['alternative_origins'][0]
        root=sources[old['source_id']]['record']['parent_wrapper_source_id']
        # A second eligible child from the same result is not another result.
        sid=add(sources,'one','observation/tool_results/0/content/stderr',
                'tool_observation','warning','a',root)
        rows.append({'submitted_quote':'warning','alternative_origins':[
            {'source_id':sid,'role':'tool_observation',
             'field_path':'observation/tool_results/0/content/stderr','event_order':23}]})
        self.assertEqual(run(rows,sources).model_input()['executions'][0]['output_fragments'],['E2','E3'])

    def test_catalog_validation_is_called_and_snapshots_frozen(self):
        rows,sources=fixture();cache={};calls=[]
        def snapshot(sid):
            if sid not in cache:
                rec=sources[sid]['record'];parent=rec['parent_wrapper_source_id']
                Record=make_dataclass('Record',[(key,object) for key in rec])
                cache[sid]=SimpleNamespace(record=Record(**rec),
                    blob=SimpleNamespace(text=sources[sid]['text']),
                    parent_wrapper=snapshot(parent) if parent else None)
            return cache[sid]
        catalog={str(i):SimpleNamespace(snapshot=snapshot(r['alternative_origins'][0]['source_id']))
                 for i,r in enumerate(rows)}
        commands=[];results=[]
        for source in sources.values():
            rec=source['record']
            if rec['parent_wrapper_source_id'] is None:
                if rec['role']=='tool_command':commands.append(source['text'])
                else:results.append({'tool_use_id':rec['tool_call_id'],'content':source['text']})
        event={'event_id':'one','sequence':23,'commands':commands,
               'observation':json.dumps({'content':'','tool_results':results})}
        digest=digest_text(json.dumps(event,sort_keys=True,ensure_ascii=False,separators=(',',':')))
        for visible in catalog.values():
            visible.snapshot.record.record_digest=digest
            visible.snapshot.parent_wrapper.record.record_digest=digest
        context=context_from_catalog(catalog,lambda c:calls.append(c),{'one':event})
        self.assertIs(calls[0],catalog)
        event['commands'].append(commands[0])
        duplicate_digest=digest_text(json.dumps(event,sort_keys=True,ensure_ascii=False,separators=(',',':')))
        for visible in catalog.values():
            visible.snapshot.record.record_digest=duplicate_digest
            visible.snapshot.parent_wrapper.record.record_digest=duplicate_digest
        duplicate=context_from_catalog(catalog,lambda c:None,{'one':event})
        self.assertEqual(project(rows,duplicate).model_input()['executions'],[])
        missing=context_from_catalog(catalog,lambda c:None,{})
        self.assertEqual(project(rows,missing).model_input()['executions'],[])
        sources.clear()
        self.assertEqual(project(rows,context).model_input()['executions'][0]['execution'],'X1')
        def reject(c):raise ValueError('native_validation_failure')
        with self.assertRaisesRegex(ValueError,'native_validation_failure'):
            context_from_catalog(catalog,reject,{'one':event})

    def test_integrity_errors_and_existing_request_shape(self):
        rows,sources=fixture(); result=run(rows,sources)
        sid=rows[0]['alternative_origins'][0]['source_id']
        sources[sid]['text']='mutated'
        with self.assertRaises(ProjectionError):run(rows,sources)
        original={'target_context_not_evidence':{'action':'update','before_entry':None},
                  'required_judgments':[{'label':'O'}],'shared_submitted_evidence_B':[]}
        updated=replace_evidence_view(original,result)
        self.assertEqual(updated['required_judgments'],original['required_judgments'])
        self.assertEqual(updated['target_context_not_evidence'],original['target_context_not_evidence'])
        self.assertEqual(original['shared_submitted_evidence_B'],[])


class CleanPairTests(unittest.TestCase):
    def test_only_plan_changes_not_fact_category_evidence_or_order(self):
        from clean_pair import pair_from_historical_B, FACT, PLAN, REFERENCE, evidence_identity
        original={'original_operation':{'action':'delete_gap','content':'old'},
                  'normative_requirements_context':'',
                  'submitted_evidence':[{'submitted_quote':'old B'}]}
        a,b=pair_from_historical_B(original)
        self.assertEqual(a['material']['original_operation']['action'],b['material']['original_operation']['action'])
        self.assertEqual(b['material']['original_operation']['content'],FACT+' '+PLAN)
        self.assertEqual(b['claims'],a['claims']+[PLAN])
        self.assertEqual(evidence_identity(a['material']),evidence_identity(b['material']))
        self.assertEqual(original['original_operation']['action'],'delete_gap')
        self.assertEqual(REFERENCE,{'fact_only':'supported','fact_plus_plan':'supported'})
        self.assertNotIn('reference',str(a))


if __name__=='__main__':unittest.main()
