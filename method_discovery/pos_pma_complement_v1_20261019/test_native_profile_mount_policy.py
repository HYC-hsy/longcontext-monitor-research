"""Offline guard regression for the native-SHARED candidate profile mount."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.pma_harbor_hooks import NativeSharedTrialHooks


class ReachedPostMountCheck(Exception):
    pass


def mount(destination, source, writable):
    return {'Destination': destination, 'Source': str(source), 'RW': writable}


class MountPolicyTests(unittest.TestCase):
    def check(self, condition, candidate, fixture, profile_fixture, with_spool,
              with_fake, expected_error=None):
        root = Path('C:/isolated-synthetic-run')
        spec = {'run_id': 'synthetic-run', 'run_root': str(root),
                'image_id': 'synthetic-image', 'condition': condition,
                'research_candidate': candidate, 'zero_model_fixture_only': fixture,
                'candidate_profile_fixture_only': profile_fixture}
        mounts = [mount('/opt/genericagent-source', 'C:/source', False),
                  mount('/opt/m4-runtime', 'C:/runtime', False)]
        if condition == 'P':
            mounts.append(mount('/run/pos-archive', root / 'control/pos_archive', True))
        if with_spool:
            mounts += [mount('/run/pma-bridge/requests', root / 'control/spool/requests', True),
                       mount('/run/pma-bridge/responses', root / 'control/spool/responses', False)]
        if with_fake:
            mounts.append(mount('/run/pos-fake-replies.json', 'C:/fake-replies', False))
        raw = {'Image': 'synthetic-image', 'HostConfig': {'NetworkMode': 'bridge'},
               'Mounts': mounts, 'Config': {'Env': []}}
        hook = NativeSharedTrialHooks.__new__(NativeSharedTrialHooks)
        hook.spec = spec
        async def inspect():
            return 'synthetic-container', raw
        async def after_mount(*_args, **_kwargs):
            raise ReachedPostMountCheck
        hook._inspect = inspect
        hook.trial = SimpleNamespace(agent=SimpleNamespace(run_id='synthetic-run'),
            agent_environment=SimpleNamespace(exec=after_mount))
        with self.assertRaises(ReachedPostMountCheck if expected_error is None else RuntimeError) as caught:
            asyncio.run(hook.agent_start(None))
        if expected_error is not None:
            self.assertIn(expected_error, str(caught.exception))

    def test_candidate_profile_fixture_mount(self):
        self.check('P', 'pos_pma_complement_v1', True, True, True, False)

    def test_candidate_formal_profile_mount(self):
        self.check('P', 'pos_pma_complement_v1', False, False, True, False)

    def test_original_pos_rejects_spool(self):
        self.check('P', 'PoS', True, False, True, True, 'GA-only Task sees PMA spool')

    def test_candidate_fake_mode_rejects_spool(self):
        self.check('P', 'pos_pma_complement_v1', True, False, True, True,
                   'GA-only Task sees PMA spool')

    def test_profile_fixture_rejects_fake_reply_mount(self):
        self.check('P', 'pos_pma_complement_v1', True, True, True, True,
                   'PoS fake reply mount differs')


if __name__ == '__main__':
    unittest.main()
