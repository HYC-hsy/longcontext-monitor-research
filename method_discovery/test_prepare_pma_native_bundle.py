import json
from pathlib import Path
import tempfile
import unittest

from prepare_pma_native_bundle import prepare, ROOT


class BundleTests(unittest.TestCase):
    def test_secret_and_controller_boundaries(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'bench_runtime') as directory:
            output = Path(directory) / 'bundle'
            identity = prepare(output, {'base': 'https://example.invalid', 'key': 'fixture-key'})
            compose = json.loads((output / 'compose.json').read_text())
            controller = compose['services']['controller']
            self.assertEqual(controller['network_mode'], 'none')
            self.assertFalse(any('/private' in v for v in controller['volumes']))
            self.assertIn('unittest', controller['command'])
            self.assertFalse(identity['task_selected'])
            self.assertNotIn('fixture-key', json.dumps(identity))
            self.assertNotIn('fixture-key', (output / 'compose.json').read_text())
            self.assertEqual(set(compose['services']), {'gateway', 'controller'})
            self.assertTrue((output / 'runtime/pma_native_entry.py').is_file())
            self.assertTrue((output / 'runtime/pma_native_support.py').is_file())


if __name__ == '__main__':
    unittest.main()
