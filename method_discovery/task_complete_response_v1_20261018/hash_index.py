"""Mechanical SHA-256 index of the public Task policy and offline evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
names = [
    'GenericAgent-main/llmcore.py',
    'GenericAgent-main/agent_loop.py',
    'GenericAgent-main/tests/test_task_complete_response.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/harbor_adapter.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/live_launcher.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/offline_launcher.py',
    'method_discovery/task_complete_response_v1_20261018/AUDIT.txt',
    'method_discovery/task_complete_response_v1_20261018/sample_offline.py',
    'method_discovery/task_complete_response_v1_20261018/hash_index.py',
]
names += ['method_discovery/task_complete_response_v1_20261018/raw/' + name for name in (
    'request_event_sample.json', 'test_unittest_stdout_stderr.txt',
    'test_pos_ga_seam_stdout_stderr.txt', 'test_pma_regression_stdout_stderr.txt',
    'test_legacy_sse_stdout_stderr.txt')]
rows = []
for name in names:
    public = subprocess.check_output(['git', 'show', ':' + name], cwd=root)
    working = (root / name).read_bytes()
    row = {'path': name, 'bytes': len(public),
           'sha256': hashlib.sha256(public).hexdigest()}
    if working != public:
        row.update({'worktree_bytes': len(working),
                    'worktree_sha256': hashlib.sha256(working).hexdigest(),
                    'identity_note': 'working tree differs from staged public blob'})
    rows.append(row)
target = Path(__file__).resolve().parent / 'raw/HASHES.json'
target.write_bytes((json.dumps({'schema': 'public-byte-hashes-v1', 'files': rows},
                               ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
