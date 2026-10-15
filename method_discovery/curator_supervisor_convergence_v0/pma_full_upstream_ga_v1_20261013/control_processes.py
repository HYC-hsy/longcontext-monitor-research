"""Host-observed GA process identities for shared-container verification.

Only Harbor-side code writes the registry. Task services are deliberately not
classified as GA control processes and are left running for SHARED verification.
"""

from __future__ import annotations

import json
import subprocess


_SCAN = r'''
import hashlib, json, os, sys
marker = 'GA_WRAPPER_RUN_ID=' + sys.argv[1]
rows = []
for name in os.listdir('/proc'):
    if not name.isdigit():
        continue
    try:
        raw = open('/proc/' + name + '/cmdline', 'rb').read()
        argv = [part.decode('utf-8', 'surrogateescape') for part in raw.split(b'\0') if part]
        kind = ('ga' if '/opt/genericagent/agentmain.py' in argv else
                'transport' if '/opt/genericagent/isolated_transport.py' in argv and
                'local' in argv else
                'wrapper' if len(argv) > 2 and os.path.basename(argv[0]) in
                {'sh', 'bash', 'dash', 'ash'} and argv[1] == '-c' and
                marker in argv[2] else None)
        if kind is None:
            continue
        stat = open('/proc/' + name + '/stat', encoding='ascii').read()
        start_ticks = stat.rsplit(') ', 1)[1].split()[19]
        rows.append({'pid': int(name), 'kind': kind, 'start_ticks': start_ticks,
                     'argv_sha256': hashlib.sha256(raw).hexdigest()})
    except (FileNotFoundError, ProcessLookupError):
        continue
print(json.dumps({'pid_namespace': os.readlink('/proc/1/ns/pid'),
                  'processes': sorted(rows, key=lambda row: row['pid'])}))
'''


def scan(container: str, python_bin: str, run_id: str) -> dict:
    result = subprocess.run(['docker', 'exec', container, python_bin, '-c', _SCAN, run_id],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('GA control process scan unavailable')
    data = json.loads(result.stdout)
    if (not isinstance(data.get('pid_namespace'), str) or
            not isinstance(data.get('processes'), list)):
        raise RuntimeError('GA control process scan malformed')
    return data


_PROBE = r'''
import hashlib, json, os, sys
expected = json.loads(sys.argv[1])
if os.readlink('/proc/1/ns/pid') != expected['pid_namespace']:
    raise SystemExit('GA PID namespace changed')
path = '/proc/%d' % expected['pid']
try:
    stat = open(path + '/stat', encoding='ascii').read()
    raw = open(path + '/cmdline', 'rb').read()
except FileNotFoundError:
    print(json.dumps({'state': 'exited'}))
    raise SystemExit(0)
start = stat.rsplit(') ', 1)[1].split()[19]
if start != expected['start_ticks']:
    print(json.dumps({'state': 'pid_reused'}))
elif hashlib.sha256(raw).hexdigest() != expected['argv_sha256']:
    print(json.dumps({'state': 'identity_changed'}))
else:
    print(json.dumps({'state': 'registered_alive'}))
'''


def probe_registered(container: str, python_bin: str, identity: dict) -> str:
    """Probe the original PID even when its current argv evades classification."""
    result = subprocess.run(['docker', 'exec', container, python_bin, '-c', _PROBE,
                             json.dumps(identity, sort_keys=True)], capture_output=True,
                            text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('registered GA process identity probe unavailable')
    try:
        state = json.loads(result.stdout)['state']
    except (ValueError, KeyError) as exc:
        raise RuntimeError('registered GA process probe malformed') from exc
    if state not in {'exited', 'pid_reused', 'identity_changed', 'registered_alive'}:
        raise RuntimeError('registered GA process probe state invalid')
    return state


_STOP = r'''
import hashlib, json, os, signal, sys
expected = json.loads(sys.argv[1])
pid = expected['pid']
try:
    raw = open('/proc/%d/cmdline' % pid, 'rb').read()
    stat = open('/proc/%d/stat' % pid, encoding='ascii').read()
except FileNotFoundError:
    raise SystemExit(0)
argv = [part.decode('utf-8', 'surrogateescape') for part in raw.split(b'\0') if part]
kind = ('ga' if '/opt/genericagent/agentmain.py' in argv else
        'transport' if '/opt/genericagent/isolated_transport.py' in argv and
        'local' in argv else
        'wrapper' if len(argv) > 2 and os.path.basename(argv[0]) in
        {'sh', 'bash', 'dash', 'ash'} and argv[1] == '-c' and
        'GA_WRAPPER_RUN_ID=' + expected['run_id'] in argv[2] else None)
if (os.readlink('/proc/1/ns/pid') != expected['pid_namespace'] or
        kind != expected['kind'] or
        stat.rsplit(') ', 1)[1].split()[19] != expected['start_ticks'] or
        hashlib.sha256(raw).hexdigest() != expected['argv_sha256']):
    raise SystemExit('GA process identity changed')
os.kill(pid, signal.SIGTERM)
'''


def stop_registered(container: str, python_bin: str, identity: dict) -> None:
    result = subprocess.run(['docker', 'exec', container, python_bin, '-c', _STOP,
                             json.dumps(identity, sort_keys=True)], capture_output=True,
                            text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('registered GA process stop failed or identity changed')
