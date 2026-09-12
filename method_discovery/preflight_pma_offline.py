"""Zero-API Linux PMA smoke check. Does not load keys or start a task agent."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import uuid


ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import importlib.metadata,json,os
from types import SimpleNamespace as NS
from pma_baseline.runtime import PMABaseline, PhaseClient
assert os.listdir('/sys/class/net') == ['lo']
assert not os.path.exists('/source/mykey.py')
assert not os.path.exists('/var/run/docker.sock')
assert importlib.metadata.version('shortuuid') == '1.0.13'
calls=[]
class Client:
 def complete(self,messages,tools):
  calls.append(messages)
  assert len(messages)==2
  if tools:
   return NS(content='',tool_calls=[NS(name='memory_save_knowledge',
    arguments='{"content":"preserve the required interface"}')])
  assert 'preserve the required interface' in messages[1]['content']
  return NS(content='<context_for_action>Check the required interface.</context_for_action>',tool_calls=[])
 def drain_telemetry(self):return {}
pma=PMABaseline('fixture task',PhaseClient(Client),'/tmp/pma')
for n in range(2):
 pma.review()
 assert 'observations, not directives' in pma.take_reminder()
 assert pma.take_reminder() is None
 pma.observe('public intent',['test command'],'public observation')
assert len(calls)==4
other=PMABaseline('new task',PhaseClient(Client))
assert not other.agent.memory.knowledge
assert list(__import__('pathlib').Path('/tmp/pma').rglob('*'))
print(json.dumps({'shortuuid':'1.0.13','only_loopback':True,
 'two_phase_rounds':2,'fake_provider_calls':len(calls),'api_calls':0,
 'one_shot_reminder':True,'fresh_task_bank_empty':True,'archive_written':True}))
'''


def run(output, runtime, image):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    runtime = Path(runtime).resolve()
    homes = list((runtime / 'python').glob('cpython-3.12.*-linux-x86_64-gnu'))
    if len(homes) != 1:
        raise ValueError('Expected one frozen Linux Python runtime')
    package = ROOT / 'GenericAgent-main/pma_baseline'
    container = 'pma-preflight-' + uuid.uuid4().hex[:10]
    report = {'api_calls': 0, 'real_task_started': False, 'container': container}
    command = ['docker', 'run', '--rm', '--name', container, '--network', 'none',
        '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--read-only',
        '--tmpfs', '/tmp:rw', '-e', 'PYTHONDONTWRITEBYTECODE=1',
        '-e', 'PYTHONPATH=/source:/opt/m4-runtime/ga-env/lib/python3.12/site-packages',
        '-v', f'{runtime.as_posix()}:/opt/m4-runtime:ro',
        '-v', f'{package.as_posix()}:/source/pma_baseline:ro', image,
        f'/opt/m4-runtime/python/{homes[0].name}/bin/python3.12', '-c', PROBE]
    try:
        identity = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
            capture_output=True, text=True, timeout=30)
        if identity.returncode:
            raise RuntimeError('Docker image inspection failed: ' + identity.stderr.strip())
        report['image_id'] = identity.stdout.strip()
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        report.update(exit_code=result.returncode, stderr=result.stderr)
        if result.returncode:
            raise RuntimeError(result.stderr[-3000:])
        report['checks'] = json.loads(result.stdout)
        report['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in package.glob('*.py')}
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        # Exact disposable fixture only; never stop other containers or Docker.
        cleanup = subprocess.run(['docker', 'rm', '-f', container],
            capture_output=True, text=True, timeout=30)
        report['cleanup_output'] = (cleanup.stdout + cleanup.stderr).strip()
        (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--runtime', default=str(ROOT / 'bench_runtime/m2/linux'))
    parser.add_argument('--image', default='debian:bookworm-slim')
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.runtime, args.image), indent=2))
