import unittest
from pma_evidence_review.focus_spans import intervals, plan
from pma_evidence_review.inputs import digest


class FocusSpanTests(unittest.TestCase):
    def check(self,text):
        spans=intervals(text)
        self.assertEqual(''.join(text[a:b] for a,b in spans),text)
        self.assertEqual(spans[0][0],0)
        self.assertEqual(spans[-1][1],len(text))
        return [text[a:b] for a,b in spans]

    def test_completion_conditions_and_mixed_clause(self):
        text='If PATH is exported, it runs. Task completed successfully. Only in this session.'
        pieces=self.check(text)
        self.assertEqual(len(pieces),3)
        self.assertIn('Task completed successfully. ',pieces)
        self.assertEqual(self.check('It exists but cross-session behavior is unknown.'),
                         ['It exists but cross-session behavior is unknown.'])

    def test_protected_punctuation_and_unicode(self):
        for text in ['Version 3.14 at /tmp/a.py and https://x.test/a?q=1.2. Done.',
            'Dr. X uses e.g. examples. Done.', 'He said "Done. Next!" yesterday. Done.',
            'Use (one. two) safely. 完成。下一步？', 'An unmatched "quote. Retain all.',
            'C:\\tools\\bin.exe is present. Fine.', '完成😀。Cafe\u0301 works.\r\nDone. Done.', 'Don\'t normalize “a。b”. 完成。']:
            self.check(text)
        self.assertEqual(len(self.check('Dr. X uses e.g. examples. Done.')),2)
        self.assertEqual(len(self.check('完成。下一步？')),2)
        self.assertEqual(len(self.check('An unmatched "quote. Retain all.')),1)

    def test_code_table_lists_and_whitespace(self):
        for text, protected in [
            ('Before.\n\n```py\na=1.2\nprint("Done.")\n```\nAfter.', '```py\na=1.2\nprint("Done.")\n```\n'),
            ('| Name | Value |\n|---|---|\n| a | b. c |\n\nDone.', '| Name | Value |\n|---|---|\n| a | b. c |\n\n'),
            ('    a=1.2\n    print("Done.")\n\nDone.', '    a=1.2\n    print("Done.")\n\n'),
            ('- Done. More details.\n- Next.\n', '- Done. More details.\n')]:
            self.assertIn(protected,self.check(text))
        for text in ['  \n\nDone. \r\n', '\n\n', '```unclosed\nDone. Next.', 'a\r\nb\r\n']:
            self.check(text)

    def test_duplicate_text_keeps_distinct_coordinates(self):
        text='Done. Done.'
        op={'op_index':0,'memory_id':'m','revision_id':'r','content':text,'content_sha256':digest(text)}
        spans=plan(op)
        self.assertEqual(len(spans),2)
        self.assertNotEqual(spans[0]['focus_id'],spans[1]['focus_id'])
        for item in spans:
            self.assertEqual(item['text'],text[item['start']:item['end']])
            self.assertEqual(item['text_sha256'],digest(item['text']))
