"""Zero-model native PMA source/dependency and optional Docker lifecycle probe."""
import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
from pma_native_trial import execute_trial

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent'


def installed_parity():
    import memory_agent
    import harbor
    results = {}
    for package, original in [(memory_agent, REFERENCE/'src/memory_agent'),
                              (harbor, REFERENCE/'external/harbor/src/harbor')]:
        installed = Path(package.__file__).parent
        checked = 0
        for source in original.rglob('*'):
            if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
                continue
            target = installed/source.relative_to(original)
            if not target.is_file() or source.read_bytes() != target.read_bytes():
                raise ValueError(f'Installed source/resource mismatch: {source.relative_to(original)}')
            checked += 1
        results[package.__name__] = checked
    return results


async def docker_probe(output):
    from harbor.models.task.task import Task
    task_dir = output/'fixture'
    (task_dir/'environment').mkdir(parents=True)
    (task_dir/'tests').mkdir()
    (task_dir/'environment/Dockerfile').write_text('FROM debian:bookworm-slim\n', encoding='utf-8')
    (task_dir/'instruction.md').write_text('Offline fixture only.', encoding='utf-8')
    (task_dir/'task.toml').write_text(
        '[environment]\ndocker_image="debian:bookworm-slim"\nallow_internet=false\n', encoding='utf-8')
    # The original Verifier uploads this script only after the fake agent stops.
    (task_dir/'tests/test.sh').write_text(
        '#!/bin/sh\nmkdir -p /logs/verifier\n'
        'if test -f /tmp/public-fixture; then echo 1 > /logs/verifier/reward.txt; '
        'else echo 0 > /logs/verifier/reward.txt; fi\n', encoding='utf-8')
    class FakeAgent:
        async def setup(self, environment):pass
        async def run(self, instruction, environment, context):
            result = await environment.exec(
                'test ! -e /tests/test.sh && touch /tmp/public-fixture', timeout_sec=10)
            assert result.return_code == 0
    return await execute_trial(Task(task_dir), None, output/'trial', 30, approved=True,
                               agent_factory=lambda *args: FakeAgent())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--docker', action='store_true')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {'api_calls': 0, 'real_task_started': False, 'status': 'checking'}
    try:
        report['installed_source_resource_parity'] = installed_parity()
        report['dependencies'] = {name: importlib.metadata.version(name) for name in
            ['memory-agent','harbor','litellm','pydantic','shortuuid','typer','PyYAML','dirhash']}
        report['reference_configs'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in (REFERENCE/'configs').glob('*.yaml')}
        if args.docker:
            report['docker'] = asyncio.run(docker_probe(output))
            assert report['docker']['evaluation_status'] == 'completed'
            assert report['docker']['reward'] == {'reward': 1.0}
        report['status'] = 'passed'
        peak = Path('/sys/fs/cgroup/memory.peak')
        if peak.is_file():
            report['controller_cgroup_peak_bytes'] = int(peak.read_text().strip())
    except Exception as exc:
        report.update(status='failed',error=str(exc))
        raise
    finally:
        (output/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':main()
