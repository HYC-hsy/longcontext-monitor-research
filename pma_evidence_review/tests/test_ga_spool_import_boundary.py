"""Import only deployed GA-side files, with no host package or installed deps."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class GASpoolImportBoundaryTests(unittest.TestCase):
    def test_minimal_ga_files_import_without_host_audit_package(self):
        root = Path(__file__).resolve().parents[2]
        stage = root/'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013'
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for source in (stage/'event_spool.py', root/'GenericAgent-main/pma_upstream_bridge.py'):
                (target/source.name).write_bytes(source.read_bytes())
            code = '''
import importlib.util, os, socket, sys
sys.path.insert(0, os.getcwd())
def forbidden(*args, **kwargs):
    raise AssertionError('network forbidden')
socket.socket.connect = forbidden
assert importlib.util.find_spec('pma_evidence_review') is None
from event_spool import EventClient
from pma_upstream_bridge import UpstreamPMAClient
os.mkdir('requests'); os.mkdir('responses')
EventClient('requests', 'responses', 'offline', 'task', deadline_monotonic=None)
UpstreamPMAClient(run_id='offline', task_id='task', requests='requests', responses='responses', deadline='uncapped')
assert 'pma_evidence_review.private_faults' not in sys.modules
print('minimal_ga_import_ok')
'''
            result = subprocess.run([sys.executable, '-I', '-S', '-c', code], cwd=target,
                                    capture_output=True, text=True, check=True, timeout=10)
            self.assertEqual(result.stdout.strip(), 'minimal_ga_import_ok')


if __name__ == '__main__':
    unittest.main()
