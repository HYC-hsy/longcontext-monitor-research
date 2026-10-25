# Copyright 2025 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Selected LangExtract helpers; modified imports only. See REUSE.md."""
from collections.abc import Sequence, Iterator
from . import tokenizer as tokenizer_lib

def _find_token_occurrences(
    source_tokens: Sequence[str],
    extraction_tokens: Sequence[str],
) -> list[int]:
  """Returns all start indices of extraction_tokens within source_tokens."""
  num_source = len(source_tokens)
  num_extraction = len(extraction_tokens)
  if num_extraction == 0 or num_source < num_extraction:
    return []
  # Normalize so the slice comparison works for any Sequence input.
  expected = list(extraction_tokens)
  first_token = expected[0]
  return [
      i
      for i in range(num_source - num_extraction + 1)
      # Cheap first-token filter before the O(m) slice compare.
      if source_tokens[i] == first_token
      and list(source_tokens[i : i + num_extraction]) == expected
  ]


def _tokenize_with_lowercase(
    text: str,
    tokenizer_inst: tokenizer_lib.Tokenizer | None = None,
) -> Iterator[str]:
  """Extract and lowercase tokens from the input text into words.

  This function utilizes the tokenizer module to tokenize text and yields
  lowercased words.

  Args:
    text (str): The text to be tokenized.
    tokenizer_inst: Optional tokenizer instance.

  Yields:
    Iterator[str]: An iterator over tokenized words.
  """
  if tokenizer_inst is not None:
    tokenized_pb2 = tokenizer_inst.tokenize(text)
  else:
    tokenized_pb2 = tokenizer_lib.tokenize(text)
  original_text = tokenized_pb2.text
  for token in tokenized_pb2.tokens:
    start = token.char_interval.start_pos
    end = token.char_interval.end_pos
    token_str = original_text[start:end]
    token_str = token_str.lower()
    yield token_str


