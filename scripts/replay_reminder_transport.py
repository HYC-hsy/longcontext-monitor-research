"""Offline replay of public memory_response.jsonl files; never invokes a model.

Usage: python scripts/replay_reminder_transport.py EXTRACTED_ARCHIVE OUTPUT_JSON
"""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py')
BASE = '7fbbf9d653d65e353e5a5d3ca29763f390911540'


def load_parser(source):
    tree = ast.parse(source)
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in {'parse_final_decision', '_mask_decision_code'}]
    namespace = {'re': re}
    exec(compile(tree, '<offline-parser>', 'exec'), namespace)
    return namespace['parse_final_decision']


def main():
    old = load_parser(subprocess.check_output(
        ['git', 'show', BASE + ':' + SOURCE.as_posix()], cwd=ROOT, text=True))
    new = load_parser((ROOT / SOURCE).read_text(encoding='utf-8'))
    results = []
    for path in sorted(Path(sys.argv[1]).rglob('memory_response.jsonl')):
        for row in map(json.loads, path.read_text(encoding='utf-8').splitlines()):
            raw = row.get('content') or ''
            match = re.search(r'<context_for_action>(.*?)</context_for_action>\s*$', raw, re.S)
            if not match:
                continue
            expected = match.group(1).strip()
            before, after = old(raw), new(raw)
            results.append({'source': str(path.relative_to(sys.argv[1])),
                'call_sequence': row['call_sequence'],
                'parent_full_match': before == ('context_for_action', expected),
                'fixed_full_match': after == ('context_for_action', expected),
                'expected_characters': len(expected),
                'parent_characters': len(before[1] or ''),
                'fixed_characters': len(after[1] or '')})
    Path(sys.argv[2]).write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    assert results and all(row['fixed_full_match'] for row in results)
    print(f'{len(results)} reminders replayed with exact bodies')


if __name__ == '__main__':
    main()
