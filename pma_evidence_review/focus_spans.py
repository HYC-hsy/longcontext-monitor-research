"""Conservative verbatim text partitions, not atomic facts or semantic coverage."""
import json
import re

from .inputs import digest, require

SPLITTER = 'verbatim-character-partition-v1'
ABBREVIATIONS = {'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'sr.', 'jr.', 'vs.', 'etc.',
                 'e.g.', 'i.e.', 'a.m.', 'p.m.', 'fig.', 'no.', 'st.'}


def sentence_ends(text):
    """Uncertain punctuation stays in a larger block; no normalization or stripping."""
    stack, ends = [], []
    pairs = {'(': ')', '[': ']', '{': '}', '“': '”', '‘': '’', '「': '」', '『': '』'}
    quote = None
    for i, char in enumerate(text):
        if quote:
            if char == quote and (i == 0 or text[i-1] != '\\'):
                quote = None
            continue
        if char in ('"', '`') or (char == "'" and not
                (i > 0 and i+1 < len(text) and text[i-1].isalnum() and text[i+1].isalnum())):
            quote = char
            continue
        if char in pairs:
            stack.append(pairs[char])
            continue
        if stack:
            if char == stack[-1]:
                stack.pop()
            continue
        if char not in '.!?。！？':
            continue
        if char in '.!?' and i+1 < len(text) and not text[i+1].isspace():
            continue
        if char == '.':
            token = text[:i+1].split()[-1].lower()
            if token in ABBREVIATIONS or any(c in token for c in '/\\@'):
                continue
            # Initials, dotted abbreviations and ellipses remain unsplit.
            if len(token) <= 2 or token.count('.') > 1:
                continue
        end = i+1
        while end < len(text) and text[end].isspace():
            end += 1
        ends.append(end)
    if stack or quote:
        return [len(text)]
    return sorted(set(ends + [len(text)]))


def intervals(text):
    """Protect fenced/indented code and tables; list lines and paragraphs are blocks."""
    require(isinstance(text, str) and bool(text), 'focus_content_missing')
    lines = text.splitlines(keepends=True)
    blocks, start, offset, mode, fence = [], 0, 0, None, None
    def flush(end, protected):
        nonlocal start
        if end > start:
            blocks.append((start, end, protected))
            start = end
    for line in lines:
        stripped = line.lstrip()
        marker = re.match(r'(`{3,}|~{3,})', stripped)
        if fence:
            offset += len(line)
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                flush(offset, True)
                fence, mode = None, None
            continue
        if marker:
            flush(offset, mode in ('table', 'code'))
            fence, mode = marker.group(1), 'fence'
            offset += len(line)
            continue
        if not line.strip():
            offset += len(line)
            flush(offset, mode in ('table', 'code'))
            mode = None
            continue
        current = ('code' if line.startswith(('    ', '\t')) else
                   'table' if '|' in line else
                   'list' if re.match(r'(?:[-*+] |\d+[.)] )', stripped) else 'prose')
        if mode != current or current == 'list':
            flush(offset, mode in ('table', 'code'))
        mode = current
        offset += len(line)
        if current == 'list':
            flush(offset, True)
    flush(len(text), mode in ('table', 'code', 'fence'))
    result = []
    for start, end, protected in blocks:
        piece = text[start:end]
        if not piece.strip() and result:
            result[-1] = (result[-1][0], end)
            continue
        previous = start
        for cut in ([end-start] if protected else sentence_ends(piece)):
            boundary = start+cut
            if boundary > previous:
                result.append((previous, boundary))
                previous = boundary
    require(result and result[0][0] == 0 and result[-1][1] == len(text) and
            all(a[1] == b[0] for a,b in zip(result,result[1:])), 'focus_partition_incomplete')
    return result


def plan(op):
    text = op['content']
    spans = []
    for start,end in intervals(text):
        identity = {k: op[k] for k in ('op_index','memory_id','revision_id','content_sha256')}
        identity.update(start=start,end=end,coordinate_unit='python_unicode_code_points')
        spans.append({**identity, 'focus_id':digest(json.dumps(identity,sort_keys=True,
            ensure_ascii=False,separators=(',',':'))), 'text':text[start:end],
            'text_sha256':digest(text[start:end]), 'splitter':SPLITTER})
    return spans
