"""Bind the reviewed isolated Sphinx path to one complete frozen source tree."""
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import zipfile

M1 = '746a695adac4325d6440941d384d543d1364fef9'
CPRR = '22755819b0a332389883f30e46e93f457a4c036c'
ROOT = Path(__file__).resolve().parents[3]
RUNNER_ROOT = Path(r'E:\longcontext-m1-746a695')

HERE = Path(__file__).resolve().parent
CORE4 = ROOT / 'method_discovery/diagnostics/m1_core4_baseline_20260929/sphinx_entry.py'
RECORDS = {
    'cprr-real-dev-pilot-20260930-05': (M1, r'E:\longcontext-m1-746a695'),
    'cprr-real-dev-pilot-20260930-06': (CPRR, r'E:\longcontext-cprr-746a695'),
}


def source(checkout, commit, destination):
    path = Path(checkout).resolve(strict=True)
    head = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    if head != commit or subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain', '--untracked-files=no']):
        raise RuntimeError('Sphinx frozen source identity mismatch')
    archive = subprocess.check_output(['git', '-C', str(path), 'archive', '--format=zip', 'HEAD', 'GenericAgent-main'])
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(io.BytesIO(archive)) as stream:
        stream.extractall(destination)
    ga = destination / 'GenericAgent-main'
    (ga / 'temp').mkdir(exist_ok=True)
    private = Path(r'E:\longcontext-m1-746a695')
    key, profile = private / 'GenericAgent-main/mykey.py', private / 'monitor_config/models.local.json'
    if hashlib.sha256(key.read_bytes()).hexdigest() != 'ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e':
        raise RuntimeError('historical private profile changed')
    shutil.copyfile(key, ga / 'mykey.py')
    (destination / 'monitor_config').mkdir()
    shutil.copyfile(profile, destination / 'monitor_config/models.local.json')
    return ga, dict(commit=head, archive_sha256=hashlib.sha256(archive).hexdigest())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True, choices=RECORDS)
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    commit, checkout = RECORDS[args.run_id]
    out = Path(args.output_root).resolve()
    dest = out / args.run_id
    if dest.exists():
        raise RuntimeError('Sphinx record already exists: no rerun')
    prereg = json.loads((HERE / 'PREREGISTRATION.json').read_text(encoding='utf-8'))
    row = [r for r in prereg['records'] if r['run_id'] == args.run_id]
    if (len(row) != 1 or row[0]['task'] != 'claw_swe:sphinx-doc__sphinx-8551'
            or row[0]['arm'] != ('m1' if commit == M1 else 'cprr')):
        raise RuntimeError('Sphinx identity differs from preregistration')
    if not args.execute and not args.prepare_only:
        print(json.dumps(dict(run_id=args.run_id, source=commit, execute=False)))
        return
    if (out / 'archive_pause.json').exists():
        raise RuntimeError('archive pause prevents new Sphinx record')
    sys.path.insert(0, str(CORE4.parent))
    spec = importlib.util.spec_from_file_location('cprr_sphinx_existing_path', CORE4)
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    entry.M1 = commit
    entry.TASK = commit
    entry.BATCH = 'cprr-real-dev-pilot-20260930'
    bundle_path = RUNNER_ROOT / 'long_context_bench/scripts/isolated_run_bundle.py'
    bundle_spec = importlib.util.spec_from_file_location('cprr_frozen_isolated_bundle', bundle_path)
    bundle_module = importlib.util.module_from_spec(bundle_spec)
    bundle_spec.loader.exec_module(bundle_module)
    build_bundle = bundle_module.build_bundle

    def exact_bundle(output, supervisor_source, policy, *, runtime_source, python_home,
                     collector_port, gateway_image, **other):
        if policy or Path(supervisor_source).resolve() != Path(checkout).resolve():
            raise RuntimeError('unexpected Sphinx treatment source or policy')
        ga, identity = source(checkout, commit, dest / 'source_input')
        copied, compose = build_bundle(output, ga, runtime_source, python_home,
            'native_claude_cc_vibe_opus48', 'claude_monitor_opus48', collector_port,
            monitor_profile_path=ga.parent / 'monitor_config/models.local.json')
        redacted_monitor = copied / 'monitor_agent_core/models.local.json'
        shutil.copyfile(redacted_monitor, Path(output) / 'virtual_monitor_profiles.json')
        topology = json.loads(compose.read_text(encoding='utf-8'))
        topology['services']['model-gateway']['image'] = gateway_image
        compose.write_text(json.dumps(topology, indent=2), encoding='utf-8')
        (dest / 'complete_source_identity.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
        return copied, compose

    entry.prepare = exact_bundle
    key_file = Path(r'E:\longcontext-m1-746a695\GenericAgent-main\mykey.py')
    values = runpy.run_path(str(key_file))
    monitor = json.loads(Path(r'E:\longcontext-m1-746a695\monitor_config\models.local.json').read_text())
    profiles = {'native_claude_cc_vibe_opus48': values['native_claude_cc_vibe_opus48'],
                'claude_monitor_opus48': monitor['claude_monitor_opus48']}
    from argparse import Namespace
    bound = Namespace(record=args.run_id, run_id=args.run_id,
                      output_root=str(out), supervisor_source=checkout)
    entry.execute(bound, profiles, prepare_only=args.prepare_only)


if __name__ == '__main__':
    main()
