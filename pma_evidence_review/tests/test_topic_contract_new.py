import json, unittest, asyncio
from pma_evidence_review.tests import test_p1_requirements as fixtures
FIXED = fixtures.FIXED
from pma_evidence_review.tests.test_bank_display import reply
from p1_requirements import assignment, topics, catalog, RequirementError
from p2_requirement_view import RequirementSelectionView

class Contract(unittest.TestCase):
    setUp = fixtures.RequirementTests.setUp
    init = fixtures.RequirementTests.init
    save = fixtures.RequirementTests.save
    reopen = fixtures.RequirementTests.reopen
    def run_cycle(self, name="c1", entries=None):
        return asyncio.run(self.agent.maintain(entries if entries is not None else [{"event_id":"build","observation":"compiled successfully"}],cycle_id=name,observation="compiled successfully"))
    def test_assignment_contract_new(self):
        self.assertEqual(topics(FIXED),FIXED)
        self.assertEqual(assignment([],FIXED),[])
        self.assertEqual(assignment([FIXED[1],FIXED[0]],FIXED),FIXED)
        for values in (['General'],['unknown']):
            with self.assertRaises(RequirementError): assignment(values,FIXED)
        with self.assertRaises(RequirementError): catalog(['General'])
    def test_actual_save_display_reopen_and_p2(self):
        self.responses=[self.init(),reply([self.save('multi',FIXED), self.save('solo',[FIXED[0]]), self.save('no topic',[])])]
        res=self.run_cycle(); self.assertEqual(res['status'],'completed')
        refs=self.agent.links.state['refs']; rows=self.agent.memory.knowledge
        self.assertEqual([refs[r.id]['requirements'] for r in rows],[FIXED,[FIXED[0]],[]])
        self.reopen(); self.responses=[reply()]; self.assertEqual(self.run_cycle('c2')['status'],'completed')
        prompt=self.requests[-1]['prompt']; self.assertNotIn('displayed memberships',prompt);self.assertNotIn('General',prompt)
        data=prompt.split('## Stored summaries (derived;',1)[1].split('\n',1)[1].split('\n## STATUS',1)[0]
        displayed=json.loads(data); by={r['content']:r for r in displayed}
        self.assertEqual(by['multi']['requirements'],FIXED);self.assertEqual(by['solo']['requirements'],[FIXED[0]])
        self.assertNotIn('requirements',by['no topic']); self.assertIn('## Fixed task topics',prompt)
        view=RequirementSelectionView(self.agent)
        initial=view.initial_records(list(view.aliases)); d={r['content']:r for r in initial}
        self.assertEqual(d['multi']['requirements'],FIXED); self.assertNotIn('requirements',d['no topic'])
        def browse(**kw):
            page=view.browse(**kw);self.assertTrue(page['page_sequence_complete']);return [json.loads(p['text']) for p in page['parts']]
        all_rows=browse(view='all',model_view=True);self.assertEqual({x['content'] for x in all_rows},{'multi','solo','no topic'})
        for topic,expected in [(FIXED[0],{'multi','solo'}),(FIXED[1],{'multi'})]:
            got=browse(view='requirement',requirement=topic,model_view=True)
            self.assertEqual({x['content'] for x in got},expected)
            self.assertEqual(next(x for x in got if x['content']=='multi')['requirements'],FIXED)
        self.assertEqual(view.browse(view='requirement',requirement='General')['status'],'unknown_requirement')
        self.assertEqual(view.browse(view='requirement',requirement='other')['status'],'unknown_requirement')
    def test_unknown_topic_cannot_save(self):
        self.responses=[self.init(),reply([self.save('bad',['not listed'])]),reply()]
        r=self.run_cycle();self.assertFalse(self.agent.memory.knowledge)
        self.assertTrue(any('invalid_requirements' in str(t) for t in r['turns']))

    def test_pagination_keeps_topics_and_unclassified(self):
        text = 'long memory \"🙂' * 1800
        self.responses = [self.init(), reply([self.save(text,FIXED),self.save('empty',[])])]
        self.assertEqual(self.run_cycle()['status'],'completed')
        view=RequirementSelectionView(self.agent)
        def read(**filters):
            parts={}; cursor=None
            for _ in range(100):
                page=view.browse(cursor=cursor,model_view=True,**filters)
                self.assertIn(page['status'],('browse_partial','browse_complete'))
                for part in page['parts']: parts.setdefault(part['source_id'],[]).append(part['text'])
                cursor=page.get('next_cursor')
                if cursor is None: return [json.loads(''.join(v)) for v in parts.values()]
            self.fail('pagination did not terminate')
        all_rows=read(view='all'); self.assertEqual(len(all_rows),2)
        long=next(r for r in all_rows if r['content']==text)
        self.assertEqual(long['requirements'],FIXED)
        empty=next(r for r in all_rows if r['content']=='empty')
        self.assertNotIn('requirements',empty)
        for topic in FIXED:
            selected=read(view='requirement',requirement=topic)
            self.assertEqual([r['content'] for r in selected],[text])

if __name__=='__main__':
    unittest.main(verbosity=2)
