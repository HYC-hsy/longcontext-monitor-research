import unittest

from .archive_plain_log_addendum import project


class PlainLogProjectionTests(unittest.TestCase):
    def test_bracketed_plain_log_and_sensitive_values(self):
        raw = (b'[stdout] useful Task text\n'
               b'[stdout] https://private.invalid/x Bearer abcdefghijkl key=other\n'
               b'[stderr] private-profile-value\n')
        public, counts = project(raw, ['private-profile-value'])
        self.assertIn(b'useful Task text', public)
        self.assertNotIn(b'private.invalid', public)
        self.assertNotIn(b'abcdefghijkl', public)
        self.assertNotIn(b'private-profile-value', public)
        self.assertEqual(counts['urls'], 1)
        self.assertEqual(counts['profile_values'], 1)

    def test_hidden_line_omitted_and_invalid_encoding_rejected(self):
        public, counts = project(b'[x] <thinking>private</thinking>\n[y] public\n', [])
        self.assertNotIn(b'private', public)
        self.assertIn(b'[y] public', public)
        self.assertEqual(counts['hidden_lines_omitted'], 1)
        with self.assertRaises(UnicodeDecodeError):
            project(b'\xff', [])


if __name__ == '__main__':
    unittest.main()
