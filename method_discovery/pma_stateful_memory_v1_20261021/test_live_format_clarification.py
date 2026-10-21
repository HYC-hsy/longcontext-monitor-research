"""A format instruction, not a change to the strict parser contract."""

import unittest

from .prompts import maintenance, repair
from .source import ContractError, strict_loads


class LiveFormatClarificationTests(unittest.TestCase):
    def test_maintenance_and_correction_explicitly_forbid_fence(self):
        original = maintenance({'example': 'input'})
        self.assertIn('raw JSON only', original[0]['content'])
        self.assertIn('no Markdown code fence', original[0]['content'])
        corrected = repair(original_messages=original, base={}, rejected='```json\n{}\n```',
                           raw_response='```json\n{}\n```', error='malformed_output',
                           mode='maintenance_contract')
        self.assertIn('do not wrap it in a Markdown code fence',
                      corrected[-1]['content'])
        self.assertEqual(corrected[:len(original)], original)

    def test_strict_parser_still_rejects_fenced_json(self):
        with self.assertRaises(ContractError):
            strict_loads('```json\n{}\n```')
        self.assertEqual(strict_loads('{}'), {})


if __name__ == '__main__':
    unittest.main()
