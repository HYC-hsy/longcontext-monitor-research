"""Reproducible local runtime cost probe; no provider calls, no performance gate."""
import json
import platform
import time
from gap_evidence_alignment import align_evidence
from test_gap_evidence_alignment import catalog_for


def main():
    text = ''.join(f'entry_{i}: task output has stable version {i}.\n' for i in range(2000))
    cases = [('structured_log', text, text[12345:12345 + size]) for size in (32, 512, 4096)]
    cases += [('repeated_punctuation', '!' * size, '!' * width)
              for size in (10000, 100000) for width in (2, 512)]
    result = []
    for label, source, quote in cases:
        catalog = catalog_for(source)
        start = time.perf_counter()
        aligned = align_evidence([{'quote': quote}], catalog)
        result.append(dict(case=label, source_chars=len(source), quote_chars=len(quote),
                           candidates=len(aligned.bound_refs), seconds=time.perf_counter() - start))
    print(json.dumps(dict(python=platform.python_version(), measurements=result), indent=2))


if __name__ == '__main__':
    main()
