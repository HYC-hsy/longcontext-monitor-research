"""One-time, pre-response private A/B assignment. Never prints the mapping."""

import argparse
import json
from pathlib import Path
import secrets

from stage1_plan import CASES, REPLICATES, sha


def balanced_pairs(random_source=None):
    """Shuffle the balanced labels, not case order or a prior assignment."""
    labels = ['current'] * 13 + ['constitution'] * 14
    (random_source or secrets.SystemRandom()).shuffle(labels)
    return [{'case_id': case, 'replicate': rep, 'A': label}
            for (case, rep), label in zip(((case, rep) for case in CASES
                                           for rep in REPLICATES), labels)]


def freeze(path: Path):
    if path.exists():
        raise ValueError('Secret blind map already exists; no redraw permitted')
    path.parent.mkdir(parents=True, exist_ok=True)
    pairs = balanced_pairs()
    raw = json.dumps({'schema_version': 'stage1-secret-blind-map/1', 'pairs': pairs},
                     ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n'
    with path.open('xb') as stream:
        stream.write(raw)
    return sha(raw)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Freeze a private pre-execution blind map')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'blind_map_commitment_sha256={freeze(args.output.resolve())}')
