"""Prepare a bounded build context; no keys, GA checkout or task data included."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT/'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent'
SCRIPTS = ('pma_native_trial.py','preflight_pma_native.py',
           'test_pma_native_contract.py','test_pma_native_trial.py',
           'pma_native_support.py', 'test_pma_native_support.py',
           'test_pma_native_wire.py', 'probe_pma_native_models.py')


def prepare(output):
    output = Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    shutil.copytree(REFERENCE,output/'reference',ignore=shutil.ignore_patterns(
        '.git','__pycache__','*.pyc','examples','.env','outputs'))
    shutil.copy2(ROOT/'method_discovery/native_controller/Dockerfile',output/'Dockerfile')
    (output/'scripts').mkdir()
    for name in SCRIPTS:
        shutil.copy2(ROOT/'method_discovery'/name,output/'scripts'/name)
    shutil.copy2(ROOT/'long_context_bench/adapters/isolated_transport.py',
                 output/'scripts/isolated_transport.py')
    inventory = {p.relative_to(output).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file()}
    (output/'build_identity.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    print(json.dumps({'build_context':str(output),'files':len(inventory),'api_calls':0}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    prepare(parser.parse_args().output)
