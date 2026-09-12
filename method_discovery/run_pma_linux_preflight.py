"""Run a zero-API native fixture in the E-drive-backed Linux controller."""
import argparse
import json
from pathlib import Path
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]


def run(label,image, scripts=None, terminal_setup_image=None):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_-' for c in label):
        raise ValueError('Use a simple unique fixture label')
    base=ROOT/'bench_runtime/pma_linux_controller/work'
    base.mkdir(parents=True,exist_ok=True)
    if (base/label).exists():
        raise FileExistsError(base/label)
    # Sibling containers are created by the Desktop daemon, not by this container.
    # Identical paths on both sides preserve upstream Harbor bind-mount semantics.
    if base.drive.upper()!='E:':
        raise ValueError('This checked Desktop mount mapping is specific to E:')
    linux_base='/run/desktop/mnt/host/e/'+base.relative_to('E:/').as_posix()
    container='pma-controller-check-'+uuid.uuid4().hex[:10]
    command=['docker','run','--rm','--name',container,'--cpus','2','--memory','2g',
        '--network','none','--read-only','--tmpfs','/tmp:rw,size=256m',
        '-v',f'{base.as_posix()}:{linux_base}',
        '-v','/var/run/docker.sock:/var/run/docker.sock',image,
        'python','-X','utf8','method_discovery/preflight_pma_native.py',
        '--output',linux_base+'/'+label,'--docker']
    if scripts:
        command[2:2] = ['-v', f'{Path(scripts).resolve().as_posix()}:/workspace/method_discovery:ro']
    if terminal_setup_image:
        command.extend(['--terminal-setup-image', terminal_setup_image])
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    report={'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
            'api_calls':0,'real_task_started':False,'cpus':2,'memory_limit_gib':2,
            'controller_network':'none','work_path':str(base/label)}
    (base/(label+'-controller.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:])
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label',required=True)
    parser.add_argument('--image',default='longcontext-pma-native:20260912-r1')
    parser.add_argument('--scripts')
    parser.add_argument('--terminal-setup-image')
    args=parser.parse_args()
    run(args.label,args.image,args.scripts,args.terminal_setup_image)
