"""Exercise authorized entry preparation with run_proof boundary fake only.

No Docker/provider/task/verifier; complements actual Linux transport receipts.
All generated authorization/provider profiles are synthetic and temporary.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

import requests
import launch_pilot as entry
from prepare_bundle import M1, TASK, POLICY_COMMIT, POLICY_PATH, blob, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--supervisor-source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--record', choices=['kitex-m1', 'kitex-m1-p'], default='kitex-m1')
    args = parser.parse_args()
    network = {'attempts': 0}
    def deny(*a, **kw):
        network['attempts'] += 1
        raise AssertionError('network forbidden in entry check')
    requests.sessions.Session.request = deny
    socket.socket.connect = deny
    socket.create_connection = deny
    original_loader = entry.load_frozen_roadmap_runner
    records = []
    def loader(directory):
        runner, imports = original_loader(directory)
        # The sole fake is the online execution boundary. Preparation, source
        # export, opt-in binding and original build_bundle all execute normally.
        def fake_run_proof(source, run_id, llm_no, seconds, task):
            assert (runner.m4.GA_ROOT / 'temp').is_dir()
            assert not any((runner.m4.GA_ROOT / 'temp').iterdir())
            copied, compose = runner.build_bundle(Path(directory) / 'checked-bundle',
                runner.m4.GA_ROOT, runner.m4.GA_RUNTIME,
                'cpython-3.12.12-linux-x86_64-gnu', 'native_claude_cc_vibe_opus48',
                'claude_monitor_opus48', runner.COLLECTOR_PORT)
            binding = json.loads((copied / 'pilot_binding.json').read_text())
            topology = json.loads(compose.read_text())
            assert not (copied / 'temp').exists()
            assert binding['monitor_commit'] == M1 and binding['task_commit'] == TASK
            assert not binding['budget_enabled'] and binding['historical_common_config']
            assert binding['policy_enabled'] == (args.record == 'kitex-m1-p')
            assert (copied / 'pilot_policy.txt').exists() == binding['policy_enabled']
            assert binding['configs']['native_claude_cc_vibe_opus48']['max_tokens'] == 64000
            assert topology['services']['main']['network_mode'] == 'none'
            assert 'PILOT_BUDGET_PATH' not in topology['services']['main']['environment']
            # Also verify pinned runner's required pre-existing substrate inputs.
            patches = runner.harbor_patch_identity()
            result = {'engineering_only': True, 'online_boundary_is_fake': True,
                'arguments': [source, run_id, llm_no, seconds, task], 'binding': binding,
                'compose': topology, 'harbor_patch_identity': patches,
                'actual_model_requests': 0}
            records.append(result)
            return result
        runner.run_proof = fake_run_proof
        return runner, imports
    entry.load_frozen_roadmap_runner = loader
    with tempfile.TemporaryDirectory(prefix='pilot-entry-check-') as temp:
        root = Path(temp)
        cfg = entry.common_profiles()
        for value in cfg.values():
            value.update(apikey='offline-virtual-key', apibase='https://offline.invalid')
        profiles = root / 'profiles.json'; profiles.write_text(json.dumps(cfg))
        auth = root / 'authorization.json'
        auth.write_text(json.dumps(dict(authorization=True, records=[args.record],
            supervisor_commit=M1, task_commit=TASK, policy_sha256=sha(blob(POLICY_COMMIT, POLICY_PATH)),
            launcher_sha256=sha(Path(entry.__file__).read_bytes()))))
        sys.argv = [entry.__file__, '--record', args.record, '--supervisor-source', args.supervisor_source,
            '--output-root', str(root / 'output'), '--profiles', str(profiles), '--authorization', str(auth), '--execute']
        entry.main()
    assert len(records) == 1 and network['attempts'] == 0
    Path(args.output).write_text(json.dumps({'scope': 'entry and bundle; online runner boundary fake',
        'records': records, 'network': network, 'actual_model_requests': 0}, indent=2))
    print(json.dumps({'entry_records': len(records), 'network_attempts': network['attempts'], 'model_requests': 0}))


if __name__ == '__main__': main()
