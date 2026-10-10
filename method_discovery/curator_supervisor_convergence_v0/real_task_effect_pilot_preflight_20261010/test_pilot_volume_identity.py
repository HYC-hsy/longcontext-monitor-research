"""No-model, same-image T/S fresh /app volume initialization check."""

from __future__ import annotations

import json
import subprocess
import unittest
import uuid


IMAGES = {
    'fyn-2.2.0-roadmap': 'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1',
    'ktx-0.13.0-roadmap': 'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e',
}
TREE_PROBE = '''import os,stat,hashlib,json
root='/app'; rows=[]
for base,dirs,files in os.walk(root,followlinks=False):
  for name in dirs+files:
    path=os.path.join(base,name); rel=os.path.relpath(path,root).replace(os.sep,'/')
    info=os.lstat(path); kind=('link' if stat.S_ISLNK(info.st_mode) else
      'dir' if stat.S_ISDIR(info.st_mode) else 'file')
    value=(os.readlink(path) if kind=='link' else
      hashlib.sha256(open(path,'rb').read()).hexdigest() if kind=='file' else '')
    rows.append((rel,kind,stat.S_IMODE(info.st_mode),value))
raw=json.dumps(sorted(rows),ensure_ascii=False,separators=(',',':')).encode()
print(json.dumps({'entries':len(rows),'sha256':hashlib.sha256(raw).hexdigest()}))'''


def docker(*args):
    return subprocess.run(['docker', *args], text=True, capture_output=True, timeout=90)


class InitialVolumeIdentity(unittest.TestCase):
    def test_fresh_task_and_supervised_volumes_match_exactly(self):
        for task, image in IMAGES.items():
            with self.subTest(task=task):
                volumes = [f'lc_pilot_init_{uuid.uuid4().hex}' for _ in range(2)]
                try:
                    identities = []
                    for volume in volumes:
                        self.assertEqual(docker('volume', 'create', volume).returncode, 0)
                        init = docker('run', '--rm', '--network', 'none', '--mount',
                                      f'type=volume,source={volume},destination=/app',
                                      '--entrypoint', 'true', image)
                        self.assertEqual(init.returncode, 0, init.stderr)
                        probe = docker('run', '--rm', '--network', 'none', '--mount',
                                       f'type=volume,source={volume},destination=/app,readonly',
                                       '--entrypoint', 'python3', image, '-c', TREE_PROBE)
                        self.assertEqual(probe.returncode, 0, probe.stderr)
                        identities.append(json.loads(probe.stdout))
                    self.assertEqual(identities[0], identities[1])
                    self.assertGreater(identities[0]['entries'], 100)
                    print(task, json.dumps(identities[0], sort_keys=True))
                finally:
                    for volume in volumes:
                        removed = docker('volume', 'rm', volume)
                        self.assertEqual(removed.returncode, 0, removed.stderr)
                        self.assertNotEqual(docker('volume', 'inspect', volume).returncode, 0)


if __name__ == '__main__':
    unittest.main()
