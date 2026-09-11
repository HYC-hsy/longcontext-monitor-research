import unittest
from paper_bundle_inventory import ROOT, selected_files, inventory


class BundleInventoryTests(unittest.TestCase):
    def test_copy_boundary(self):
        paths = [p.relative_to(ROOT / 'GenericAgent-main') for p in selected_files(ROOT / 'GenericAgent-main')]
        self.assertTrue(paths)
        self.assertFalse(any(p.name.startswith('mykey') for p in paths))
        self.assertFalse(any('temp' == p.parts[0] or 'tests' in p.parts for p in paths))
        self.assertTrue(any(p.as_posix() == 'memory/global_mem_insight.txt' for p in paths))
        self.assertFalse(any(p.parts[0] == 'memory' and len(p.parts) > 2 for p in paths))

    def test_report_does_not_certify_or_expose_content(self):
        report = inventory()
        self.assertFalse(report['is_clean_baseline_certification'])
        self.assertEqual(report['files_selected'], len(report['files']))
        for row in report['files']:
            self.assertNotIn('content', row)
            self.assertEqual(row['semantic_review'], 'not_certified')
            if not row['credential_pattern_review_required']:
                self.assertEqual(len(row['sha256']), 64)


if __name__ == '__main__':
    unittest.main()
