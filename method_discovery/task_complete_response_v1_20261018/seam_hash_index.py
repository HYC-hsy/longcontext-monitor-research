"""Index final staged public blob bytes without rewriting earlier evidence."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
names = [
    'GenericAgent-main/llmcore.py',
    'GenericAgent-main/agent_loop.py',
    'GenericAgent-main/tests/test_task_complete_response.py',
    'method_discovery/task_complete_response_v1_20261018/SEAM_AUDIT.txt',
    'method_discovery/task_complete_response_v1_20261018/seam_hash_index.py',
]
names += ['method_discovery/task_complete_response_v1_20261018/raw/' + name
          for name in ('seam_unittest_stdout_stderr.txt',
                       'seam_pos_ga_stdout_stderr.txt',
                       'seam_pma_stdout_stderr.txt')]
rows = []
for name in names:
    public = subprocess.check_output(['git', 'show', ':' + name], cwd=root)
    working = (root / name).read_bytes()
    row = {'path': name, 'bytes': len(public),
           'sha256': hashlib.sha256(public).hexdigest()}
    if public != working:
        row.update({'worktree_bytes': len(working),
                    'worktree_sha256': hashlib.sha256(working).hexdigest(),
                    'line_content_equal': public.splitlines() == working.splitlines()})
    rows.append(row)
target = Path(__file__).resolve().parent / 'raw/SEAM_HASHES.json'
target.write_bytes((json.dumps({'schema': 'seam-public-byte-hashes-v1',
                                'files': rows}, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
