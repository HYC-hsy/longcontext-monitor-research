"""Focused offline evaluator projection checks; no model or native tests."""
import hashlib
import unittest
from unittest.mock import patch

from . import evaluation_bootstrap as bootstrap


class OfflineOcamlProjectionTests(unittest.TestCase):
    def test_pinned_git_blob_becomes_offline_without_changing_test_suffix(self):
        original = (bootstrap.PREPARATION_PREFIX + bootstrap.TEST_BOUNDARY +
            b'git clone https://github.com/sadiqj/ocaml/ ocaml-original && cd ocaml-original && '
            b'git checkout tag_purposefully_broken_sweeping_changes && cd ..\n'
            b'make clean && ./configure && make -j4\n'
            b'pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py\n')
        with patch.object(bootstrap, 'OCAML_SHA256', hashlib.sha256(original).hexdigest()):
            projected = bootstrap.effective_script(original, task='fix-ocaml-gc')
        self.assertIn(b'cp -a /var/cache/evaluation-ocaml-original ocaml-original', projected)
        self.assertNotIn(b'git clone', projected)
        self.assertIn(b'export UV_OFFLINE=1', projected)
        self.assertIn(b'export UV_PYTHON_DOWNLOADS=never', projected)
        self.assertTrue(projected.endswith(b'make clean && ./configure && make -j4\n'
                                        b'pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py\n'))

    def test_unpinned_bytes_rejected(self):
        with self.assertRaises(bootstrap.BootstrapFailed):
            bootstrap.effective_script(b'#!/bin/bash\n', task='fix-ocaml-gc')
