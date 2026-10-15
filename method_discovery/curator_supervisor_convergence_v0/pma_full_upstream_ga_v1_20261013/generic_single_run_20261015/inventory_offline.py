"""Host-only fixed-Git inventory for the 12 selected tasks; no test execution."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.offline_launcher import image_identity
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.six_task_assets import descriptor


TASK_ORDER = (
    'constraints-scheduling', 'financial-document-processor', 'git-multibranch',
    'adaptive-rejection-sampler', 'query-optimize', 'raman-fitting',
    'write-compressor', 'build-cython-ext', 'nginx-request-logging',
    'pypi-server', 'sqlite-with-gcov', 'reshard-c4-data',
)


def inventory(source: Path) -> dict:
    rows = []
    for task in TASK_ORDER:
        official = descriptor(source, task, registered=True)
        image = image_identity(official['image_tag'])
        repo = official['image_tag'].rsplit(':', 1)[0]
        digests = [value for value in image['repo_digests']
                   if value.startswith(repo + '@sha256:')]
        if len(digests) != 1:
            raise RuntimeError(f'{task}: official local image digest not unique')
        rows.append({**official, 'image_id': image['image_id'],
                     'repo_digest': digests[0], 'platform': image['platform'],
                     'image_task_material_visibility': 'not_checked_in_this_inventory',
                     'native_verifier_executed': False,
                     'agent_timeout_multiplier_for_14400_seconds':
                        14400 / official['native_agent_seconds'],
                     'verifier_timeout_multiplier': 1})
    return {'schema': 'pma-ga-fixed-task-inventory-v1',
            'execution_authorized': False, 'tasks': rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--official-source-git', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inventory(args.official_source_git.resolve(strict=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({'tasks': len(result['tasks']), 'execution_authorized': False}))


if __name__ == '__main__':
    main()
