"""Zero-model process-boundary checks for the two-task extension."""

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from .pma_harbor_hooks import _nginx_service_only
from .two_task_plan import SCHEMA, validate_plan


HEADER = "UID PID PPID C STIME TTY TIME CMD"
BASE = "root 10 1 0 00:00 ? 00:00:00 sleep 120"
MASTER = "root 20 1 0 00:00 ? 00:00:00 nginx: master process /usr/sbin/nginx"
WORKER = "www 21 20 0 00:00 ? 00:00:00 nginx: worker process"
WRITER = "root 22 1 0 00:00 ? 00:00:00 python task_writer.py"


class NginxServiceBoundary(TestCase):
    def test_only_binary_verified_nginx_survives(self):
        output = "\n".join((HEADER, BASE, MASTER, WORKER))
        with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout='[{"pid":20,"ppid":1,"exe":"/usr/sbin/nginx"},'
                                      '{"pid":21,"ppid":20,"exe":null}]')) as run:
            self.assertTrue(_nginx_service_only("container-id", output, {"10"}))
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["docker", "exec", "container-id", "python3"])
        self.assertNotIn("kill", " ".join(command))

    def test_extra_writer_or_executable_mismatch_fails_closed(self):
        output = "\n".join((HEADER, BASE, MASTER, WORKER))
        with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout='[{"pid":20,"ppid":1,"exe":"/usr/sbin/nginx"},'
                                      '{"pid":21,"ppid":20,"exe":null}]')):
            self.assertFalse(_nginx_service_only(
                "container-id", output + "\n" + WRITER, {"10"}))
        with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout='[{"pid":20,"ppid":1,"exe":"/usr/sbin/nginx"}]')):
            self.assertFalse(_nginx_service_only("container-id", output, {"10"}))
        with patch("subprocess.run", return_value=SimpleNamespace(
                returncode=1, stdout="")):
            self.assertFalse(_nginx_service_only("container-id", output, {"10"}))

    def test_no_new_service_is_not_an_exemption(self):
        with patch("subprocess.run") as run:
            self.assertFalse(_nginx_service_only(
                "container-id", "\n".join((HEADER, BASE)), {"10"}))
        run.assert_not_called()


class TwoTaskIdentity(TestCase):
    def test_exact_slots_and_unique_roots(self):
        arms = [dict(order=1, task='rstan-to-pystan', repeat=1, condition='B'),
                dict(order=2, task='nginx-request-logging', repeat=1, condition='B')]
        manifest = {'schema': SCHEMA, 'execution_authorized': False,
                    'code_commit': 'code', 'config_sha256': 'config',
                    'planned_order': arms}
        authorized = {'execution_authorized': True, 'approved_arms': arms,
                      'audited_code_commit': 'code', 'config_sha256': 'config',
                      'run_bindings': [dict(arm, run_id=f'run-{i}',
                                            run_root=f'/tmp/pma-two-{i}',
                                            config_sha256='config')
                                       for i, arm in enumerate(arms)]}
        self.assertEqual(validate_plan(manifest, authorized),
                         authorized['run_bindings'])
        authorized['run_bindings'][1]['run_root'] = authorized['run_bindings'][0]['run_root']
        with self.assertRaisesRegex(RuntimeError, 'reused'):
            validate_plan(manifest, authorized)

    def test_old_panel_cannot_be_relabelled_two_task(self):
        manifest = {'schema': SCHEMA, 'execution_authorized': False,
                    'planned_order': [dict(order=1, task='db-wal-recovery',
                                           repeat=1, condition='B')]}
        with self.assertRaisesRegex(RuntimeError, 'order'):
            validate_plan(manifest, {'execution_authorized': True,
                                     'approved_arms': manifest['planned_order'],
                                     'run_bindings': []})
