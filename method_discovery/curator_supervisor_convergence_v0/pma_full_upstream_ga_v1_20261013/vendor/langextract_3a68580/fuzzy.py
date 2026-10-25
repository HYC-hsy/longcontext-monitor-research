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

"""Verbatim pinned LangExtract LCS subset; see REUSE.md."""
import math
import typing
from collections.abc import Sequence

_FUZZY_ALIGNMENT_MIN_THRESHOLD = 0.75
_FUZZY_ALIGNMENT_MIN_DENSITY = 1 / 3

class LcsSpan(typing.NamedTuple):
  """Result of _best_lcs_span: matched token count and source span."""

  matches: int
  start: int
  end: int

  @property
  def span_len(self) -> int:
    return 0 if self.start < 0 else self.end - self.start + 1


def _best_lcs_spans(
    source: Sequence[str],
    extraction: Sequence[str],
) -> dict[int, LcsSpan]:
  """Finds the tightest source span for each achievable match count.

  Runs an O(n * m^2) time / O(m^2) memory DP with rolling rows on the
  i dimension. For each (i, j, k), tracks the latest source index s
  such that source[s..i) contains at least k tokens of extraction[0..j)
  as a subsequence. Preferring later starts produces minimum-span
  results; among spans of equal length, the earliest start wins.
  Tracking per match count lets the caller try a denser k-1 match if
  the maximum-match span fails a density gate.

  Args:
    source: Normalized source tokens.
    extraction: Normalized extraction tokens.

  Returns:
    Dict mapping each achievable match count k (1..m) to its tightest
    LcsSpan. Empty dict if no matches found.
  """
  n = len(source)
  m = len(extraction)
  if n == 0 or m == 0:
    return {}

  # Rolling rows: prev_row[j][k] holds span_start[i-1][j][k],
  # curr_row[j][k] holds span_start[i][j][k]. k=0 is trivially
  # achievable: at i, source[i..i) is empty, so s=i gives 0 matches.
  prev_row = [[-1] * (m + 1) for _ in range(m + 1)]
  curr_row = [[-1] * (m + 1) for _ in range(m + 1)]
  for j in range(m + 1):
    prev_row[j][0] = 0  # i=0 base: k=0 achievable with s=0

  # best_per_k[k] = tightest span seen so far with exactly k matches.
  best_per_k: dict[int, LcsSpan] = {}

  for i in range(1, n + 1):
    src_tok = source[i - 1]
    # Initialize column j=0 of curr_row: k=0 achievable with s=i, k>0 not.
    curr_row[0][0] = i
    for k in range(1, m + 1):
      curr_row[0][k] = -1

    for j in range(1, m + 1):
      curr_row[j][0] = i
      matches_here = src_tok == extraction[j - 1]
      for k in range(1, m + 1):
        skip_source = prev_row[j][k]
        skip_extraction = curr_row[j - 1][k]
        best = skip_source if skip_source > skip_extraction else skip_extraction
        if matches_here:
          if k == 1:
            match_cand = i - 1
          else:
            match_cand = prev_row[j - 1][k - 1]
          best = max(best, match_cand)
        curr_row[j][k] = best

    end = i - 1
    for k in range(1, m + 1):
      s = curr_row[m][k]
      if s < 0:
        continue
      existing = best_per_k.get(k)
      if existing is None:
        best_per_k[k] = LcsSpan(matches=k, start=s, end=end)
        continue
      new_len = end - s + 1
      cur_len = existing.span_len
      if new_len < cur_len or (new_len == cur_len and s < existing.start):
        best_per_k[k] = LcsSpan(matches=k, start=s, end=end)

    prev_row, curr_row = curr_row, prev_row

  return best_per_k


def _accept_lcs_match(
    span: LcsSpan,
    extraction_len: int,
    threshold: float = _FUZZY_ALIGNMENT_MIN_THRESHOLD,
    min_density: float = _FUZZY_ALIGNMENT_MIN_DENSITY,
) -> bool:
  """Applies coverage and density gates to an LCS result.

  Coverage gate (threshold): did we find enough of the extraction?
  Requires matches >= ceil(extraction_len * threshold).

  Density gate (min_density): is the match tight enough? Requires
  matches / span_len >= min_density, rejecting scattered matches
  where matched tokens are spread across too much noise.

  Args:
    span: LcsSpan result from _best_lcs_span.
    extraction_len: Number of tokens in the extraction.
    threshold: Minimum fraction of the extraction that must match.
    min_density: Minimum ratio of matched tokens to span length.
  """
  if span.matches == 0 or extraction_len == 0:
    return False
  needed = math.ceil(extraction_len * threshold)
  if span.span_len <= 0:
    return False
  density = span.matches / span.span_len
  return span.matches >= needed and density >= min_density


