"""MIT: eea/rag-facts-check b78a082; see RAG_LICENSE. Function copied unchanged."""
def merge_overlapping_spans(
    spans: list[tuple[int, int]],
    max_gap: int = 0,
) -> list[tuple[int, int]]:
    """Merge spans that overlap or touch each other.

    Multiple evidence quotes for one claim can point at the same passage (or at
    adjacent passages). Downstream renderers split text on segment boundaries,
    so overlapping spans duplicate text. Merging keeps one highlight per
    passage.

    Args:
        spans: List of ``(start, end)`` offsets (end exclusive), unordered.
        max_gap: Also merge spans separated by at most this many characters.

    Returns:
        Sorted list of disjoint, non-touching ``(start, end)`` spans.
    """
    merged: list[list[int]] = []
    for start, end in sorted(spans):
        if end <= start:
            continue
        if merged and start <= merged[-1][1] + max_gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]

