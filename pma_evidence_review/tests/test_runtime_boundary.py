"""Full event/persistence chain, scripted clients only; not semantic evaluation."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pma_evidence_review.tests.runtime_boundary_support import wrapper
from pma_evidence_review.tests.no_network import install_guard
from episode import PMAEpisode
from event_spool import EventDispatcher
from worker_main import install_transport_audit
from pma_evidence_review import claim_split_semantic as v4, claim_split_simple as v3
from pma_evidence_review import claim_split, execution_link
from pma_evidence_review.citation_inputs import identity


def event(kind, sequence, **fields):
    return dict(schema='pma-ga-events-v1', run_id='offline-run', task_id='offline-task',
                kind=kind, sequence=sequence, event_id='e'+str(sequence), **fields)


def assert_json(test, value):
    encoded = json.dumps(value, allow_nan=False)
    test.assertNotIn('audit_execution_context', encoded)
    test.assertNotIn('frozen_sources', encoded)
    test.assertNotIn('frozen_inventory', encoded)
    return encoded


class RuntimeBoundaryTests(unittest.TestCase):
    def setUp(self):
        install_guard(self)

    def test_full_episode_report_durable_roundtrip(self):
        for repair, intervene in ((False, False), (True, False), (False, True)):
            with self.subTest(repair=repair, intervene=intervene), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor, calls = wrapper(root, repair=repair, intervene=intervene)
                episode = PMAEpisode(actor, run_id='offline-run', task_id='offline-task', archive=root/'private')
                install_transport_audit(actor, episode.archive)
                start = event('task_start', 1, initial_user_content='Synthetic task')
                if os.environ.get('PMA_EXPECT_BASELINE_FAILURE'):
                    with self.assertRaisesRegex(TypeError, 'Context'):
                        asyncio.run(episode.handle(start))
                    self.assertIn('diagnostic_write_error', actor._memory_agent.last_citation_gate_report)
                    self.assertIsInstance(actor._memory_agent.last_citation_gate_report['operations'][0]
                        ['attempts'][0]['split']['request']['audit_execution_context'], execution_link.Context)
                    self.assertTrue((episode.archive/'events.jsonl').is_file())
                    continue
                async def run():
                    from pma_evidence_review.private_faults import EpisodeFault
                    with self.assertRaises(EpisodeFault):
                        await episode.handle({**start, 'sequence': 9})
                    self.assertIsNone(episode._failure)  # pre-accept validation is recoverable
                    self.assertEqual(calls, [])
                    result = await episode.handle(start)
                    self.assertEqual(result['status'], 'started')
                    before = await episode.handle(event('before_actor_call', 2, actor_attempt=1))
                    self.assertEqual(before['status'], 'reminder' if intervene else 'silent')
                    step = event('actor_step', 3, actor_attempt=1, step_status='normal', response='public',
                        commands=[json.dumps(dict(id='call-alpha', tool_name='code_run',
                            args=dict(script='echo alpha\necho unselected-private-witness')))],
                        observation=json.dumps(dict(content='public', tool_results=[dict(tool_use_id='call-alpha',
                            content=json.dumps(dict(status='ok', stdout='alpha-output')))])))
                    self.assertEqual((await episode.handle(step))['status'], 'observed')
                    self.assertEqual((await episode.handle(event('task_end', 4, terminal='offline-complete')))['status'], 'saved')
                    self.assertEqual(episode.finalize_without_event('cleanup')['status'], 'not_saved')
                asyncio.run(run())
                gate = actor._memory_agent
                assert_json(self, gate.last_citation_gate_report)
                assert_json(self, gate.last_evidence_report)
                self.assertTrue(gate.last_citation_gate_report['operations'][0]['success'])
                batch_rows = [r for r in gate.review_transport.records if r['phase'] == 'citation_claim_verify_batch']
                self.assertTrue(batch_rows)
                self.assertTrue(all(r['operation_kind'] == 'save' for r in batch_rows))
                self.assertTrue(all(r['effective_payload_sha256'] == r['audit_request_sha256'] for r in batch_rows))
                self.assertEqual(episode.last_sequence, 4)
                self.assertTrue(episode.ended)
                # Every gate request/reply/cycle and complete episode gap report is parsed.
                for path in (root/'review').glob('*.jsonl'):
                    for line in path.read_text().splitlines():
                        assert_json(self, json.loads(line))
                for line in (episode.archive/'gap_cycle.jsonl').read_text().splitlines():
                    assert_json(self, json.loads(line))
                self.assertEqual(len((episode.archive/'events.jsonl').read_text().splitlines()), 4)
                for line in (episode.archive/'memory_payload.jsonl').read_text().splitlines():
                    assert_json(self, json.loads(line))
                # The model payload itself is the safe projection, not host witness.
                reviews = [kw for phase, kw in calls if phase == 'citation_review'
                           and kw['prompt'].startswith('TARGET AND SHARED')]
                linked = json.loads(reviews[-1]['prompt'].split('\n', 1)[1])['shared_submitted_evidence_B']
                self.assertEqual(linked['executions'][0]['command_fragments'], ['E1'])
                self.assertEqual(linked['executions'][0]['output_fragments'], ['E2'])
                for kw in reviews:
                    self.assertNotIn('unselected-private-witness', assert_json(self, kw))
                self.assertEqual(sum(p == 'citation_repair' for p, _ in calls), int(repair))

    def test_v3_generic_call_preserves_request_compatibility(self):
        from pma_evidence_review.transport import CapturedTransport, FakeClient
        material = dict(original_operation=dict(op_index=0), submitted_evidence=[], normative_requirements_context={})
        request = v3.split_request(material, 0)
        result = asyncio.run(v3.split_stage(request, CapturedTransport(FakeClient(['["claim"]']))))
        self.assertEqual(result['split']['request'], request)
        generic = dict(request, additional_legacy_metadata={'untouched': [1]})
        row = asyncio.run(claim_split._call(generic, CapturedTransport(FakeClient(['ok']))))
        self.assertEqual(row['request'], generic)
        self.assertEqual(identity({k: request[k] for k in ('prompt', 'system', 'tools')}), request['audit_request_sha256'])


    def dispatcher(self, root, **options):
        actor, calls = wrapper(root, **options)
        episode = PMAEpisode(actor, run_id='offline-run', task_id='offline-task', archive=root/'private')
        requests, responses = root/'requests', root/'responses'
        requests.mkdir(); responses.mkdir()
        start = event('task_start', 1, initial_user_content='Synthetic task')
        (requests/'e1.json').write_text(json.dumps(start))
        return actor, calls, episode, EventDispatcher(episode, requests, responses), start

    def test_dispatcher_success_receipt_and_failed_receipt_write_never_reexecute(self):
        import event_spool
        from pma_evidence_review.private_faults import EpisodeFault
        for broken_receipt in (False, True):
            with self.subTest(broken_receipt=broken_receipt), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor, calls, episode, dispatcher, start = self.dispatcher(root)
                if broken_receipt:
                    with patch.object(event_spool, '_atomic_json', side_effect=OSError('private endpoint/key')):
                        with self.assertRaises(EpisodeFault):
                            asyncio.run(dispatcher.serve_once())
                    self.assertFalse((root/'responses/e1.json').exists())
                    self.assertEqual(episode.last_sequence, 1)  # completed, receipt unavailable
                    count = len(calls)
                else:
                    count = None
                self.assertEqual(asyncio.run(dispatcher.serve_once()), 1)
                receipt = json.loads((root/'responses/e1.json').read_text())
                self.assertEqual(receipt['status'], 'ok')
                self.assertEqual(receipt['result']['status'], 'started')
                self.assertEqual(asyncio.run(dispatcher.serve_once()), 0)
                if count is not None:
                    self.assertEqual(len(calls), count)
                self.assertEqual(asyncio.run(episode.handle(start))['status'], 'started')

    def test_audit_write_failures_safe_receipt_terminal_event_no_repeat(self):
        from pma_evidence_review import transport
        import citation_gate_agent
        from pma_evidence_review.private_faults import EpisodeFault
        for filename in ('gate_cycles.jsonl', 'requests.jsonl', 'responses.jsonl'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor, calls, episode, dispatcher, start = self.dispatcher(root)
                real_durable = transport.durable
                def broken(path, row):
                    if Path(path).name == filename:
                        raise OSError('SECRET endpoint and key')
                    return real_durable(path, row)
                with patch.object(transport, 'durable', side_effect=broken), patch.object(citation_gate_agent, 'durable', side_effect=broken):
                    self.assertEqual(asyncio.run(dispatcher.serve_once()), 1)
                response = json.loads((root/'responses/e1.json').read_text())
                self.assertEqual(response['status'], 'error')
                self.assertEqual(set(response), {'status', 'error_type', 'failure_id', 'run_id', 'task_id', 'event_id'})
                self.assertNotIn('SECRET', json.dumps(response))
                self.assertEqual(episode.last_sequence, 0)
                self.assertNotIn('e1', episode._responses)
                count = len(calls)
                self.assertEqual(asyncio.run(dispatcher.serve_once()), 0)
                with self.assertRaises(EpisodeFault):
                    asyncio.run(episode.handle(start))
                with self.assertRaises(EpisodeFault):
                    asyncio.run(episode.handle(event('task_end', 2, terminal='failed')))
                self.assertEqual(len(calls), count)
                failures = list((root/'review/private_failures').glob('failure-*.json')) + list((episode.archive/'private_failures').glob('failure-*.json'))
                self.assertTrue(any('SECRET' in p.read_text() and 'Traceback' in p.read_text() for p in failures))
                self.assertTrue(all(p.stat().st_mode & 0o077 == 0 for p in failures))
                # Cleanup remains explicitly non-inference and does not claim task success.
                self.assertEqual(episode.finalize_without_event('audit_failed')['status'], 'saved_without_task_end')
                self.assertEqual(len(calls), count)

    def test_gap_cycle_write_failure_after_event_record_is_not_start_success(self):
        from pma_evidence_review.private_faults import EpisodeFault
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actor, calls, episode, dispatcher, start = self.dispatcher(root)
            original_open = Path.open
            def fail_gap(path, *args, **kwargs):
                if path.name == 'gap_cycle.jsonl':
                    raise OSError('PRIVATE_GAP_WRITE_ERROR')
                return original_open(path, *args, **kwargs)
            with patch.object(Path, 'open', new=fail_gap):
                asyncio.run(dispatcher.serve_once())
            response = json.loads((root/'responses/e1.json').read_text())
            self.assertEqual(response['status'], 'error')
            self.assertEqual(response['error_type'], 'OSError')
            self.assertEqual(episode.last_sequence, 0)
            intermediate = json.loads((episode.archive/'events.jsonl').read_text())
            self.assertEqual(intermediate['result']['status'], 'started')
            private = json.loads((episode.archive/'private_failures'/('failure-'+response['failure_id']+'.json')).read_text())
            self.assertEqual(private['event_id'], 'e1')
            self.assertIn('PRIVATE_GAP_WRITE_ERROR', private['traceback'])
            count = len(calls)
            with self.assertRaises(EpisodeFault):
                asyncio.run(episode.handle(start))
            self.assertEqual(len(calls), count)

    def test_exception_private_traceback_and_failed_private_diagnostic_are_safe(self):
        import pma_evidence_review.private_faults as faults
        for diagnostic_failure in (False, True):
            with self.subTest(diagnostic_failure=diagnostic_failure), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                actor, calls, episode, dispatcher, start = self.dispatcher(root)
                async def fail(_):
                    local_secret = 'LOCAL_SECRET_MUST_NOT_BE_CAPTURED'
                    raise TypeError('SECRET_EXCEPTION_MESSAGE')
                with patch.object(episode, '_task_start', side_effect=fail):
                    if diagnostic_failure:
                        with patch.object(faults, 'os', wraps=faults.os) as private_os:
                            private_os.open.side_effect = OSError('SECOND_SECRET')
                            asyncio.run(dispatcher.serve_once())
                    else:
                        asyncio.run(dispatcher.serve_once())
                response = json.loads((root/'responses/e1.json').read_text())
                self.assertEqual(response['status'], 'error')
                self.assertEqual(response['error_type'], 'TypeError')
                self.assertNotIn('SECRET', json.dumps(response))
                self.assertEqual(calls, [])
                path = episode.archive/'private_failures'/('failure-'+response['failure_id']+'.json')
                if diagnostic_failure:
                    self.assertFalse(path.exists())
                    self.assertFalse(episode._failure['diagnostic_saved'])
                else:
                    private = json.loads(path.read_text())
                    self.assertIn('SECRET_EXCEPTION_MESSAGE', private['traceback'])
                    self.assertIn('Traceback', private['traceback'])
                    self.assertNotIn("local_secret =", private['traceback'])
                self.assertEqual(asyncio.run(dispatcher.serve_once()), 0)

    def test_worker_fatal_private_audit_failure_keeps_traceback_without_success(self):
        import worker_main
        from types import SimpleNamespace as NS
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actor, calls = wrapper(root)
            shared = root/'shared'
            requests, responses = shared/'requests', shared/'responses'
            requests.mkdir(parents=True); responses.mkdir()
            (requests/'e1.json').write_text(json.dumps(event('task_start', 1, initial_user_content='Synthetic task')))
            args = NS(private_root=str(root/'worker'), requests=str(requests), responses=str(responses),
                      run_id='offline-run', task_id='offline-task', fake_memory=False, deadline_epoch=None,
                      research_candidate='pma_gap_evidence_v1')
            original_getfile = worker_main.inspect.getfile
            def source_path(obj):
                # Optional Harbor import double has no vendored file; only bypass
                # this path attestation for that double, never production execution.
                if obj is worker_main.Terminus2 and obj.__module__ == 'pma_evidence_review.tests.runtime_boundary_support':
                    return str(Path(worker_main.__file__).parent/'vendor/pma_89e5c0d/external/harbor/src/import-double.py')
                return original_getfile(obj)
            with patch.dict(os.environ, {}, clear=True), patch.object(worker_main.inspect, 'getfile', side_effect=source_path), patch.object(worker_main, 'construct_upstream', return_value=actor), patch.object(worker_main, 'append_private_audit', side_effect=worker_main.PMAAuditIntegrityError('PRIVATE_FATAL')):
                with self.assertRaises(worker_main.PMAAuditIntegrityError):
                    asyncio.run(worker_main.serve(args))
            self.assertEqual(calls, [])
            self.assertFalse((responses/'e1.json').exists())
            exit_row = json.loads((root/'worker/worker_exit.json').read_text())
            self.assertFalse(exit_row['task_end_saved'])
            failure = root/'worker/private_failures'/('failure-'+exit_row['failure_id']+'.json')
            self.assertIn('PRIVATE_FATAL', json.loads(failure.read_text())['traceback'])
            self.assertNotIn('PRIVATE_FATAL', json.dumps(exit_row))

    def test_effective_request_hashes_are_actual_send_payload_not_legacy_template(self):
        import hashlib
        from pma_evidence_review.transport import CapturedTransport, FakeClient
        from pma_evidence_review import operation_audit
        with tempfile.TemporaryDirectory() as tmp:
            transport = CapturedTransport(FakeClient(['ok', 'ok']), tmp, fake=True)
            for action in ('save', 'update'):
                batch = operation_audit.prepare('frozen-'+action,
                    dict(action=action, arguments=dict(content='fact')), None, ['fact'], [], '')
                payload = dict(system=operation_audit.system_for(batch), prompt='material', tools=None)
                request = dict(payload, phase='citation_claim_verify_batch', operation_kind=action,
                               audit_request_sha256=identity(payload))
                asyncio.run(transport.send(request))
            records = [json.loads(x) for x in (Path(tmp)/'requests.jsonl').read_text().splitlines()]
            self.assertNotEqual(records[0]['effective_system_sha256'], records[1]['effective_system_sha256'])
            for row in records:
                self.assertEqual(row['effective_system_sha256'], hashlib.sha256(row['request']['system'].encode()).hexdigest())
                self.assertEqual(row['effective_payload_sha256'], identity(row['request']))
                self.assertEqual(row['audit_request_sha256'], identity(row['request']))
                self.assertEqual(row['phase'], 'citation_claim_verify_batch')
                self.assertIn(row['operation_kind'], ('save', 'update'))

    def test_v4_split_dto_excludes_runtime_even_when_nested_call_log_is_serialized(self):
        from pma_evidence_review.transport import CapturedTransport, FakeClient
        context = execution_link.Context('PRIVATE FULL WITNESS', '{}')
        request = dict(system='split', prompt='only target', tools=None, phase='citation_claim_split',
                       audit_request_sha256='preserved', audit_execution_context=context,
                       audit_operation_kind='update', audit_before_entry={'content': 'old'})
        result = asyncio.run(v4.split_stage(request, CapturedTransport(FakeClient(['["claim"]']))))
        assert_json(self, result)
        self.assertNotIn('PRIVATE FULL WITNESS', json.dumps(result))
        self.assertIs(request['audit_execution_context'], context)
        self.assertEqual(result['split']['request'], {k: v for k, v in request.items() if k != 'audit_execution_context'})


if __name__ == '__main__':
    unittest.main()
