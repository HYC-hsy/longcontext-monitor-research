"""Local Git autocrlf roundtrip; synthetic bytes, no model/profile/network."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013 import collect_single_run_fixture as collector


class CertificateByteTests(unittest.TestCase):
    def test_collector_index_and_actual_autocrlf_checkout_preserve_bytes(self):
        def git(root,*args):
            return subprocess.check_output(['git','-c','user.name=Offline Fixture',
                '-c','user.email=fixture@localhost','-c','commit.gpgsign=false',*args],cwd=root,
                stderr=subprocess.STDOUT)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir()
            git(repo,'init');git(repo,'config','--local','core.autocrlf','true')
            output=repo/'evidence/gate-only'
            original={'A/raw.jsonl':b'{"raw":"line one"}\r\n{"raw":"line two"}\r\n',
                      'B/gate_certificate.json':'{"schema":"synthetic","text":"中文"}\n'.encode('utf-8')}
            def collect(condition,source,target,secrets,*unused):
                target.mkdir()
                records=[]
                for name,data in original.items():
                    if name.startswith(condition+'/'):
                        (output/name).write_bytes(data)
                        records.append({'path':name,'bytes':len(data),
                            'sha256':hashlib.sha256(data).hexdigest(),'redactions':0})
                return records
            argv=['collector','--a','unused','--b','unused','--output',str(output),
                  '--task-profile-file','unused','--pma-profile-file','unused']
            with patch('sys.argv',argv),patch.object(collector,'private_values',return_value=[]),\
                    patch.object(collector,'collect',side_effect=collect),\
                    patch.object(collector,'verify_evidence',return_value={'outcomes':{'A':{},'B':{}}}):
                collector.main()
            original['.gitattributes']=b'* -text\n'
            index=json.loads((output/'FILE_HASHES.json').read_text(encoding='utf-8'))
            self.assertEqual({r['path'] for r in index['files']},set(original))
            for row in index['files']:
                self.assertEqual(row['sha256'],hashlib.sha256(original[row['path']]).hexdigest())
            original['FILE_HASHES.json']=(output/'FILE_HASHES.json').read_bytes()
            git(repo,'add','--','evidence');git(repo,'commit','-m','Synthetic evidence')
            for name,data in original.items():
                self.assertEqual(git(repo,'show','HEAD:evidence/gate-only/'+name),data)
            # A fresh real checkout with autocrlf enabled before files are written.
            checkout=root/'fresh'
            git(root,'clone','--no-hardlinks','--config','core.autocrlf=true',str(repo),str(checkout))
            self.assertEqual(git(checkout,'config','--get','core.autocrlf').strip(),b'true')
            for name,data in original.items():
                path=checkout/'evidence/gate-only'/name
                self.assertEqual(path.read_bytes(),data,name)
                attribute=git(checkout,'check-attr','text','--',path.relative_to(checkout).as_posix())
                self.assertTrue(attribute.rstrip().endswith(b'text: unset'))
            self.assertTrue(git(checkout,'check-attr','text','--','outside.txt').rstrip().endswith(b'text: unspecified'))
            self.assertEqual(git(checkout,'status','--porcelain'),b'')
