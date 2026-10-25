"""Cheap cross-source candidate organization before pinned block-local LCS.

The lexical ranking is a PMA adapter, not an upstream LangExtract feature.
Source text is never normalized here. Each window stays in one visible span.
"""
from collections import Counter
from fractions import Fraction

from vendor.langextract_3a68580.chunking import (
    create_token_interval, get_char_interval, iter_fragment_intervals)
from vendor.langextract_3a68580.tokenizer import RegexTokenizer

POLICY = "lexical_ranked_visible_windows_v1"
BASE_CHAR_BUFFER = 1000


def ranked_windows(target, catalog):
    """Return all viable windows, safe-pruned count and generated count.

    Multiset overlap is an upper bound on LCS matches, not a semantic score.
    With density >= 1/3 an accepted span contains at most 3*m tokens. Expanding
    each base fragment by 3*m-1 tokens on either side protects boundary spans.
    Very long windows may still exceed the LCS budget and must be reported.
    """
    target_counts = Counter(target)
    minimum = (3 * len(target) + 3) // 4  # ceil(.75*m), upstream default
    expansion = max(0, 3 * len(target) - 1)
    windows, pruned, generated = [], 0, 0
    for visible in catalog.values():
        for offset, end in visible.visible_spans:
            chunk = visible.snapshot.blob.text[offset:end]
            tokenized = RegexTokenizer().tokenize(chunk)
            tokens = tokenized.tokens
            source = [chunk[t.char_interval.start_pos:t.char_interval.end_pos]
                      for t in tokens]
            seen = set()
            for base in iter_fragment_intervals(tokenized, BASE_CHAR_BUFFER):
                first = max(0, base.start_index - expansion)
                last = min(len(tokens), base.end_index + expansion)
                if (first, last) in seen:
                    continue
                seen.add((first, last))
                generated += 1
                lexical = source[first:last]
                overlap = sum((Counter(lexical) & target_counts).values())
                if overlap < minimum:
                    pruned += 1
                    continue
                interval = get_char_interval(tokenized, create_token_interval(first, last))
                # Rational comparisons and source identity make insertion order
                # irrelevant even at a tight computational budget.
                rank = (-Fraction(overlap, max(1, len(target))),
                        -Fraction(overlap, max(1, len(lexical))),
                        visible.snapshot.record.source_id,
                        offset + interval.start_pos, offset + interval.end_pos,
                        visible.visibility_ref)
                windows.append((rank, visible, offset, lexical, tokens[first:last]))
    windows.sort(key=lambda row: row[0])
    return windows, {"policy": POLICY, "generated_windows": generated,
                     "lexically_pruned_windows": pruned}
