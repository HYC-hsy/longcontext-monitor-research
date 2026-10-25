# Copyright 2025 Google LLC.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Modified upstream test cases, unittest instead of absl; see vendor REUSE.md."""
import unittest
from vendor.langextract_3a68580 import tokenizer
from vendor.langextract_3a68580.alignment import _find_token_occurrences, _tokenize_with_lowercase


class UpstreamAdaptedTests(unittest.TestCase):
    def test_regex_tokenizer_upstream_cases(self):
        # tests/tokenizer_test.py:44-157; same inputs, types and newline flags.
        cases = [
            ("Hello, world!", [0, 2, 0, 2], []),
            ("Age:   25\nWeight=70kg.", [0, 2, 1, 0, 2, 1, 0, 2], [3]),
            ("Line1\nLine2\nLine3", [0, 1, 0, 1, 0, 1], [2, 4]),
            ("!!!@#   $$$%", [2, 2, 2, 2, 2], []),
            ("", [], []), ("café", [0], []), ("?!", [2, 2], []),
        ]
        for text, kinds, newline_indices in cases:
            with self.subTest(text=text):
                result = tokenizer.tokenize(text)
                self.assertEqual([t.token_type for t in result.tokens], kinds)
                self.assertEqual([t.index for t in result.tokens if t.first_token_after_newline], newline_indices)
                self.assertTrue(all(text[t.char_interval.start_pos:t.char_interval.end_pos] for t in result.tokens))

    def test_repeated_mentions_preserve_candidates_not_dp_selection(self):
        # Adapted tests/resolver_test.py:2608-2619. Deliberate policy difference:
        # upstream DP assigns successive mentions; this helper keeps both.
        source = "Take aspirin in the morning. Take aspirin at night."
        first_start = source.index("aspirin")
        second_start = source.index("aspirin", first_start + 1)
        tokenized = tokenizer.tokenize(source)
        occurrences = _find_token_occurrences(list(_tokenize_with_lowercase(source)), ["aspirin"])
        self.assertEqual([tokenized.tokens[i].char_interval.start_pos for i in occurrences],
                         [first_start, second_start])

    def test_token_exact_is_not_literal_exact(self):
        source = "Aspirin   daily"
        self.assertEqual(_find_token_occurrences(list(_tokenize_with_lowercase(source)),
                                                list(_tokenize_with_lowercase("aspirin daily"))), [0])
        self.assertNotEqual(source, "aspirin daily")


if __name__ == "__main__":
    unittest.main()
