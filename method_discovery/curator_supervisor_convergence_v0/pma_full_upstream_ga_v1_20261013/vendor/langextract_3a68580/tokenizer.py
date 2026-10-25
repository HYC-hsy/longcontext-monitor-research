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

"""Selected upstream tokenizer code; modified by removing debug decorator and
unused exports/error/sentence/Unicode-tokenizer code. See REUSE.md.
"""
import abc
import dataclasses
import enum
import regex

@dataclasses.dataclass(slots=True)
class CharInterval:
  """Represents a range of character positions in the original text.

  Attributes:
    start_pos: The starting character index (inclusive).
    end_pos: The ending character index (exclusive).
  """

  start_pos: int
  end_pos: int


@dataclasses.dataclass(slots=True)
class TokenInterval:
  """Represents an interval over tokens in tokenized text.

  The interval is defined by a start index (inclusive) and an end index
  (exclusive).

  Attributes:
    start_index: The index of the first token in the interval.
    end_index: The index one past the last token in the interval.
  """

  start_index: int = 0
  end_index: int = 0


class TokenType(enum.IntEnum):
  """Enumeration of token types produced during tokenization.

  Attributes:
    WORD: Represents an alphabetical word token.
    NUMBER: Represents a numeric token.
    PUNCTUATION: Represents punctuation characters.
  """

  WORD = 0
  NUMBER = 1
  PUNCTUATION = 2


@dataclasses.dataclass(slots=True)
class Token:
  """Represents a token extracted from text.

  Each token is assigned an index and classified into a type (word, number,
  punctuation, or acronym). The token also records the range of characters
  (its CharInterval) that correspond to the substring from the original text.
  Additionally, it tracks whether it follows a newline.

  Attributes:
    index: The position of the token in the sequence of tokens.
    token_type: The type of the token, as defined by TokenType.
    char_interval: The character interval within the original text that this
      token spans.
    first_token_after_newline: True if the token immediately follows a newline
      or carriage return.
  """

  index: int
  token_type: TokenType
  char_interval: CharInterval = dataclasses.field(
      default_factory=lambda: CharInterval(0, 0)
  )
  first_token_after_newline: bool = False


@dataclasses.dataclass
class TokenizedText:
  """Holds the result of tokenizing a text string.

  Attributes:
    text: The text that was tokenized. For UnicodeTokenizer, this is
      NOT normalized to NFC (to preserve indices).
    tokens: A list of Token objects extracted from the text.
  """

  text: str
  tokens: list[Token] = dataclasses.field(default_factory=list)


_LETTERS_PATTERN = r"[^\W\d_]+"
_DIGITS_PATTERN = r"\d+"
# Group identical symbols (e.g. "!!") but split mixed ones.
_SYMBOLS_PATTERN = r"([^\w\s]|_)\1*"
_END_OF_SENTENCE_PATTERN = regex.compile(r"[.?!。！？\u0964][\"'”’»)\]}]*$")

_TOKEN_PATTERN = regex.compile(
    rf"{_LETTERS_PATTERN}|{_DIGITS_PATTERN}|{_SYMBOLS_PATTERN}"
)
_WORD_PATTERN = regex.compile(rf"(?:{_LETTERS_PATTERN}|{_DIGITS_PATTERN})\Z")

# Abbreviations that do not end sentences.
# TODO: Evaluate removal for large-context use cases.
_KNOWN_ABBREVIATIONS = frozenset({"Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "St."})
_CLOSING_PUNCTUATION = frozenset({'"', "'", "”", "’", "»", ")", "]", "}"})


class Tokenizer(abc.ABC):
  """Abstract base class for tokenizers."""

  @abc.abstractmethod
  def tokenize(self, text: str) -> TokenizedText:
    """Splits text into tokens.

    Args:
      text: The text to tokenize.

    Returns:
      A TokenizedText object.
    """


class RegexTokenizer(Tokenizer):
  """Regex-based tokenizer (default).

  The RegexTokenizer is faster than UnicodeTokenizer for English text because it
  skips involved Unicode handling.
  """

  def tokenize(self, text: str) -> TokenizedText:
    """Splits text into tokens (words, digits, or punctuation).

    Each token is annotated with its character position and type. Tokens
    following a newline or carriage return have `first_token_after_newline`
    set to True.

    Args:
      text: The text to tokenize.

    Returns:
      A TokenizedText object containing all extracted tokens.
    """
    tokenized = TokenizedText(text=text)
    previous_end = 0
    for token_index, match in enumerate(_TOKEN_PATTERN.finditer(text)):
      start_pos, end_pos = match.span()
      matched_text = match.group()
      token = Token(
          index=token_index,
          char_interval=CharInterval(start_pos=start_pos, end_pos=end_pos),
          token_type=TokenType.WORD,
          first_token_after_newline=False,
      )
      if token_index > 0:
        # Optimization: Check gap without slicing.
        has_newline = text.find("\n", previous_end, start_pos) != -1
        if not has_newline:
          has_newline = text.find("\r", previous_end, start_pos) != -1
        if has_newline:
          token.first_token_after_newline = True
      if regex.fullmatch(_DIGITS_PATTERN, matched_text):
        token.token_type = TokenType.NUMBER
      elif _WORD_PATTERN.fullmatch(matched_text):
        token.token_type = TokenType.WORD
      else:
        token.token_type = TokenType.PUNCTUATION
      tokenized.tokens.append(token)
      previous_end = end_pos
    return tokenized


# Default tokenizer instance for backward compatibility
_DEFAULT_TOKENIZER = RegexTokenizer()


def tokenize(
    text: str, tokenizer: Tokenizer = _DEFAULT_TOKENIZER
) -> TokenizedText:
  """Splits text into tokens using the provided tokenizer (default: RegexTokenizer).

  Args:
    text: The text to tokenize.
    tokenizer: The tokenizer instance to use.

  Returns:
    A TokenizedText object.
  """
  return tokenizer.tokenize(text)


