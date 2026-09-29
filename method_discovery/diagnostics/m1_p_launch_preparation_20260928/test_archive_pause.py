"""Admission checks; no provider, Docker or credential access."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import launch_pilot
from prepare_bundle import M1, TASK, blob, sha, POLICY_COMMIT, POLICY_PATH


class PauseTest(unittest.TestCase):
    def test_archive_pause_blocks_next_record_before_profiles_or_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            auth=dict(authorization=True, records=['kitex-m1-p'], supervisor_commit=M1, task_commit=TASK,
                launcher_sha256=sha(Path(launch_pilot.__file__).read_bytes()),
                policy_sha256=sha(blob(POLICY_COMMIT,POLICY_PATH)))
            (root/'auth.json').write_text(json.dumps(auth))
            (root/'archive_pause.json').write_text('{"reason":"synthetic archive failure"}')
            argv=['launch_pilot.py','--record','kitex-m1-p','--supervisor-source',str(root/'absent-source'),
                  '--output-root',str(root),'--execute','--authorization',str(root/'auth.json'),
                  '--profiles',str(root/'must-not-be-read.json')]
            with patch('sys.argv',argv), patch.object(launch_pilot,'load_frozen_roadmap_runner') as load:
                with self.assertRaisesRegex(RuntimeError,'prior archive failure pauses'):
                    launch_pilot.main()
                load.assert_not_called()
            self.assertFalse((root/'kitex-m1-p').exists())

    def test_authorization_still_required(self):
        with self.assertRaisesRegex(RuntimeError,'not authorized'):
            launch_pilot.authorize(None,'kitex-m1')


if __name__ == '__main__': unittest.main()
