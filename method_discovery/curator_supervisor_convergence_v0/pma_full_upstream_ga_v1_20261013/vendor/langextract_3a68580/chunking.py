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

"""Pinned chunk interval helpers and adapted newline/token fragment splitting.

create_token_interval: upstream chunking.py:143-166 unchanged.
get_char_interval: upstream chunking.py:216-243, only CharInterval import changed.
iter_fragment_intervals adapts ChunkIterator.__next__:441-484 to an already
visible source span, without Document/sentence inference/provider dependencies.
It preserves the upstream newline preference and indivisible long-token rule.
"""
from . import tokenizer as tokenizer_lib

def create_token_interval(
    start_index: int, end_index: int
) -> tokenizer_lib.TokenInterval:
  """Creates a token interval.

  Args:
    start_index: first token's index (inclusive).
    end_index: last token's index + 1 (exclusive).

  Returns:
    Token interval.

  Raises:
    ValueError: If the token indices are invalid.
  """
  if start_index < 0:
    raise ValueError(f"Start index {start_index} must be positive.")
  if start_index >= end_index:
    raise ValueError(
        f"Start index {start_index} must be < end index {end_index}."
    )
  return tokenizer_lib.TokenInterval(
      start_index=start_index, end_index=end_index
  )


def get_char_interval(
    tokenized_text: tokenizer_lib.TokenizedText,
    token_interval: tokenizer_lib.TokenInterval,
) -> tokenizer_lib.CharInterval:
  """Returns the char interval corresponding to the token interval.

  Args:
    tokenized_text: Document.
    token_interval: Token interval.

  Returns:
    Char interval of the token interval of interest.

  Raises:
    ValueError: If the token_interval is invalid.
  """
  if token_interval.start_index >= token_interval.end_index:
    raise ValueError(
        f"Start index {token_interval.start_index} must be < end index "
        f"{token_interval.end_index}."
    )
  start_token = tokenized_text.tokens[token_interval.start_index]
  # Penultimate token prior to interval.end_index
  final_token = tokenized_text.tokens[token_interval.end_index - 1]
  return tokenizer_lib.CharInterval(
      start_pos=start_token.char_interval.start_pos,
      end_pos=final_token.char_interval.end_pos,
  )


def iter_fragment_intervals(tokenized_text, max_char_buffer=1000):
    """Yield nonoverlapping token intervals; never change the original text.

    Unlike upstream ChunkIterator, no prose sentence grouping is attempted:
    these are source-code/terminal fragments. Query overlap is added separately.
    """
    if max_char_buffer <= 0:
        raise ValueError("max_char_buffer must be positive")
    tokens = tokenized_text.tokens
    start = 0
    while start < len(tokens):
        current = create_token_interval(start, start + 1)
        first = get_char_interval(tokenized_text, current)
        if first.end_pos - first.start_pos > max_char_buffer:
            yield current
            start += 1
            continue
        start_of_new_line = -1
        for token_index in range(start, len(tokens)):
            if tokens[token_index].first_token_after_newline:
                start_of_new_line = token_index
            candidate = create_token_interval(start, token_index + 1)
            chars = get_char_interval(tokenized_text, candidate)
            if chars.end_pos - chars.start_pos > max_char_buffer:
                if start_of_new_line > start:
                    current = create_token_interval(start, start_of_new_line)
                break
            current = candidate
        yield current
        start = current.end_index
