"""Single-factor isolation, not a new semantic dataset or labeled experiment."""
import ast
import asyncio
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import types
import unittest
import zipfile

from pma_evidence_review import operation_review as candidate
from pma_evidence_review.inputs import validate
from pma_evidence_review.location import locate
from pma_evidence_review.transport import CapturedTransport, FakeClient
from pma_evidence_review.tests.no_network import install_guard

BASELINE = '77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7'
ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'pma_evidence_review/operation_review.py'


def baseline_source():
    # Read pinned trusted implementation only, never code from a trajectory archive.
    return subprocess.check_output(['git', 'show', BASELINE + ':' + SOURCE],
                                   cwd=ROOT).decode('utf-8')


def comparison(contract):
    start = contract.index('Audit the complete original operation,')
    start = contract.index('\n', start) + 1
    end = contract.index('For deletion the fixed question')
    return contract[start:end]


class PromptCandidateTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_only_comparison_constant_and_strategy_change_in_production(self):
        old, new = ast.parse(baseline_source()), ast.parse((ROOT/SOURCE).read_text(encoding='utf-8'))
        def normalized(tree):
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    name = node.targets[0].id
                    if name == 'STRATEGY':
                        node.value = ast.Constant('VERSION')
                    if name == 'CONTRACT':
                        text = node.value.value
                        node.value = ast.Constant(text.replace(comparison(text), 'COMPARISON\n', 1))
            return ast.dump(tree, include_attributes=False)
        self.assertEqual(normalized(old), normalized(new))
        changed = subprocess.check_output(['git','diff',BASELINE,'--name-only','--',
            'pma_evidence_review/*.py','pma_evidence_review/vendor'],cwd=ROOT).decode().splitlines()
        self.assertEqual(changed,[SOURCE])

    def test_frozen_inputs_requests_and_baseline_replay_isolated(self):
        module = types.ModuleType('pma_evidence_review.pinned_baseline')
        module.__package__ = 'pma_evidence_review'
        exec(compile(baseline_source(), BASELINE + '/' + SOURCE, 'exec'), module.__dict__)
        archive = ROOT/'pma_evidence_review/diagnostic_packages/PMA_AUDITOR_V4_DIRECT_REAL_DIAGNOSTIC_20261026.zip'
        self.assertEqual(archive.stat().st_size,270673)
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
            'adc43e5719cbdc7a0aa1ac3766d07f79722fb1256c59c704fb611f03a6836f28')
        identities = {'sqlite':'0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90',
            'html':'4760d69e0e47f1e0ede15e9fd800270b89768a6307c45b4c8d4223803cc1494b'}
        before = comparison(module.CONTRACT)
        after = comparison(candidate.CONTRACT)
        for label in ('SQLite','sqlite','HTML','tarball','SVG','regex','op0','op1','Doc6','gold','holdout'):
            self.assertNotIn(label,after)
        with zipfile.ZipFile(archive) as z:
            for sample,count in [('sqlite',3),('html',4)]:
                p=json.loads(z.read(sample+'-input.json'))
                validate(p)
                self.assertEqual(p['review_input_sha256'],identities[sample])
                a,b=module.operation_requests(p),candidate.operation_requests(p)
                self.assertEqual(len(a),count)
                for old,new in zip(a,b):
                    old,new=copy.deepcopy(old),copy.deepcopy(new)
                    for plan in (old,new):
                        payload={k:plan['request'][k] for k in ('system','prompt','tools')}
                        actual=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,
                            separators=(',',':')).encode('utf-8')).hexdigest()
                        self.assertEqual(actual,plan['request']['audit_request_sha256'])
                    self.assertNotEqual(old['request']['audit_request_sha256'],new['request']['audit_request_sha256'])
                    self.assertEqual(new['request']['prompt'].count(after),1)
                    new['request']['prompt']=new['request']['prompt'].replace(after,before,1)
                    new['request']['review_strategy']=old['request']['review_strategy']
                    new['request']['audit_request_sha256']=old['request']['audit_request_sha256']
                    self.assertEqual(old,new)  # target/registry/context/example/order/budget/fields
                replies=[json.dumps({'op_index':i,'verdict':'NOT_ENOUGH_INFO',
                    'explanation':'Scripted plumbing probe; no semantic label.','evidence':[]}) for i in range(count)]
                for version in (module,candidate):
                    client=FakeClient(replies)
                    report=asyncio.run(version.review(p,CapturedTransport(client,fake=True),locator=locate))
                    self.assertEqual(len(client.calls),count)
                    self.assertEqual(report['schema'],candidate.SCHEMA)
                    for plan,actual in zip(version.operation_requests(p),client.calls):
                        self.assertEqual(actual,{k:plan['request'][k] for k in ('prompt','system','tools')})
