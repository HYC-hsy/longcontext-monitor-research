"""Offline RJC-v0 checks: ledger replay on archived runs and episode wiring with fakes.

No model, Task or evaluator is called. Archived runs are read-only fixtures.
"""
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / 'pos_pma_complement_v1_20261019'),
                str(ROOT / 'pos_upstream_ga_v1_20261017'),
                str(ROOT / 'pos_upstream_ga_v1_20261017/vendor'),
                str(ROOT / ('curator_supervisor_convergence_v0/'
                    'pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src'))]
from episode import PoSEpisode, execution_config  # noqa: E402
from memory_agent.memory.trigger import MemoryAgentTrigger, TriggerConfig  # noqa: E402
from memory_agent.memory.universal_memory import UniversalMemory  # noqa: E402
from memory_adapter import SharedViewMemoryAgent  # noqa: E402
from failure_ledger import FailureLedger, LIMITS, command_tokens  # noqa: E402
from rjc_view import RJCBeliefManager, RJCEpisode, RJCSentinel  # noqa: E402

ARCHIVES = {
    'pos-68764e': ROOT / ('pos_pma_shared_view_v1_20261020/raw_live_sqlite_contract_v2/'
                          'pos/events.host.jsonl.part001.jsonl'),
    'pos-41c50c': ROOT / ('pos_pma_shared_view_v1_20261020/raw_live_sqlite_httpdiag_v2_split/'
                          'pos/events.host.jsonl.part001.jsonl'),
    'pos-bcb35740': ROOT / ('pos_upstream_ga_v1_20261017/raw_final_two_v2/03/'
                            'pos_host/events.host.jsonl.part001.jsonl'),
}
SQLITE_TASK = ('Compile SQLite in /app/sqlite with gcov instrumentation and make it '
               'available in the PATH.\nThe SQLite source snapshot is pre-vendored at '
               '/app/vendor/sqlite-fossil-release.tar.gz; use it instead of fetching '
               'sources over the network.\n')

INITIAL = {'goal_specification': 'sqlite3 on PATH.',
           'entities': [{'entity_id': 'e1', 'entity_type': 'software', 'name': 'sqlite3'}],
           'states': [], 'relations': [], 'epistemic_gaps': [],
           'achievement_gaps': [{'target': 'sqlite3 available in PATH',
                                 'reason': 'not yet verified'}],
           'frontier': {'gap_type': 'achievement', 'target': 'sqlite3 available in PATH'}}
KEEP = {'remove_state_ids': [], 'remove_relation_ids': [], 'upsert_entities': [],
        'upsert_states': [], 'upsert_relations': [], 'epistemic_gaps': [],
        'achievement_gaps': INITIAL['achievement_gaps'], 'frontier': INITIAL['frontier']}
CLOSE = {**KEEP, 'achievement_gaps': [], 'frontier': None}


class Logger:
    def __init__(self): self.rows = []
    def log(self, event, **data): self.rows.append((event, data))


class SyncRole:
    def __init__(self, replies): self.replies, self.requests = list(replies), []
    def __call__(self, messages):
        self.requests.append(messages)
        return self.replies.pop(0)


class AsyncRole:
    def __init__(self, replies): self.replies, self.requests = list(replies), []
    async def call(self, **kwargs):
        self.requests.append(kwargs)
        return self.replies.pop(0)


def response(content='', calls=()):
    return SimpleNamespace(content=content, tool_calls=list(calls))


def tool(name, arguments):
    return SimpleNamespace(function=SimpleNamespace(name=name, arguments=arguments))


def receipt(tool_id, script, *, stdout='', stderr='', exit_code=0, name='code_run'):
    action = {'id': tool_id, 'name': name, 'arguments': {'type': 'bash', 'script': script},
              'order': 0, 'status': 'executed'}
    source = {'origin': 'GA_tool_outcome', 'tool_use_id': tool_id, 'status': 'executed',
              'result': {'status': 'success' if exit_code == 0 else 'error',
                         'stdout': stdout, 'stderr': stderr, 'exit_code': exit_code}}
    return action, source


def replay_archive(path, goal):
    """Feed archived host events (tool_started + tool_outcome) into a ledger."""
    ledger = FailureLedger(goal)
    turns = {}
    for line in path.open(encoding='utf-8'):
        row = json.loads(line)
        payload = row.get('payload', {})
        turn = payload.get('turn')
        if row.get('kind') == 'tool_started':
            turns.setdefault(turn, {'actions': [], 'sources': []})['actions'].append(
                {'id': payload['id'], 'name': payload['name'], 'order': payload.get('order', 0),
                 'arguments': payload.get('arguments') or {}, 'status': 'executed'})
        elif row.get('kind') == 'tool_outcome':
            turns.setdefault(turn, {'actions': [], 'sources': []})['sources'].append(
                {'origin': 'GA_tool_outcome', 'tool_use_id': payload['tool_use_id'],
                 'status': payload.get('status'), 'result': payload.get('result')})
    for turn in sorted(turns):
        ledger.ingest(turn=turn, transition_id=f'actor-transition-{turn}',
                      action_batch=turns[turn]['actions'], source_events=turns[turn]['sources'])
    return ledger


class LedgerReplayTests(unittest.TestCase):
    def test_sqlite_failure_pairs_match_archive_facts(self):
        ledger = replay_archive(ARCHIVES['pos-68764e'], SQLITE_TASK)
        sqlite = [r for r in ledger.records if 'sqlite3' in r['tokens']]
        self.assertEqual(len(sqlite), 2)
        self.assertTrue(all(r['goal_relevant'] for r in sqlite))
        self.assertTrue(all(r['closed_by'] is not None for r in sqlite))
        closers = {r['closed_by']['receipt_id'] for r in sqlite}
        self.assertEqual(len(closers), 1)
        self.assertIn('bash -l -c', sqlite[0]['closed_by']['closing_script_head'])
        self.assertIn('command not found', sqlite[0]['fail_lines'][0])
        # The pairing exposes both invocation contexts, not just script heads.
        self.assertEqual(sqlite[0]['failing_invocation_lines'], ['which sqlite3', 'sqlite3 --version'])
        self.assertEqual(sqlite[0]['closed_by']['closing_invocation_lines'],
                         ["bash -l -c 'which sqlite3 && sqlite3 --version'",
                          '/app/sqlite/bin/sqlite3 --version'])
        section = json.loads(ledger.panel_section().split('\n', 1)[1])
        self.assertEqual([item['failure_id'] for item in section['items']], ['F4', 'F5'])
        self.assertEqual(section['omitted'], 0)
        self.assertEqual(ledger.open_records(), [])
        open_any = ledger.open_records(goal_relevant_only=False)
        self.assertEqual([r['tokens'] for r in open_any], [['file']])
        review = ledger.completion_review(open_gaps=[{'target': 'SQLite binary available in PATH'}],
                                          stale=True)
        self.assertTrue(review['fires'])
        self.assertIn('bash -l -c', review['prompt'])
        self.assertTrue(all(item['goal_relevant'] for item in review['items']))

    def test_correct_run_and_old_run_do_not_fire_without_gaps(self):
        for name in ('pos-bcb35740', 'pos-41c50c'):
            ledger = replay_archive(ARCHIVES[name], SQLITE_TASK)
            self.assertFalse(any('sqlite3' in r['tokens'] for r in ledger.records), name)
            self.assertEqual(ledger.open_records(), [], name)
            review = ledger.completion_review(open_gaps=[], stale=False)
            self.assertFalse(review['fires'], name)
            self.assertNotIn('prompt', review)
        # The correct run has no goal-relevant failure at all; the old run has
        # closed gcc/gcov/make failures, so its panel shows closures only.
        self.assertEqual(replay_archive(ARCHIVES['pos-bcb35740'], SQLITE_TASK).panel_section(), '')
        old = replay_archive(ARCHIVES['pos-41c50c'], SQLITE_TASK).panel_section()
        self.assertIn('closed_by_receipt', old)
        self.assertNotIn('"status":"open"', old)

    def test_model_text_cannot_close_and_only_later_receipt_can(self):
        ledger = FailureLedger(SQLITE_TASK)
        a1, s1 = receipt('t1', 'sqlite3 --version',
                         stdout='bash: line 1: sqlite3: command not found', exit_code=127)
        ledger.ingest(turn=1, transition_id='a1', action_batch=[a1], source_events=[s1])
        self.assertEqual(ledger.tag_for_now(), ['F1'])
        # A same-turn or earlier success never closes; a non-code_run never closes.
        a0, s0 = receipt('t0', 'which sqlite3', stdout='/app/sqlite/bin/sqlite3')
        ledger.ingest(turn=1, transition_id='a1b', action_batch=[a0], source_events=[s0])
        self.assertEqual(ledger.tag_for_now(), ['F1'])
        a2, s2 = receipt('t2', 'sqlite3 --version', stdout='3.50.4', name='update_working_checkpoint')
        ledger.ingest(turn=2, transition_id='a2', action_batch=[a2], source_events=[s2])
        self.assertEqual(ledger.tag_for_now(), ['F1'])
        # A later successful receipt invoking the command closes and keeps both scripts.
        a3, s3 = receipt('t3', "bash -l -c 'which sqlite3'", stdout='/app/sqlite/bin/sqlite3')
        summary = ledger.ingest(turn=3, transition_id='a3', action_batch=[a3], source_events=[s3])
        self.assertEqual(summary['closed'], ['F1'])
        pair = ledger.records[0]
        self.assertEqual(pair['failing_script_head'], 'sqlite3 --version')
        self.assertIn("bash -l -c 'which sqlite3'", pair['closed_by']['closing_script_head'])
        self.assertEqual(pair['closed_by']['closing_invocation_lines'],
                         ["bash -l -c 'which sqlite3'"])
        self.assertIn('F1', ledger.panel_section())
        self.assertLessEqual(len(ledger.panel_section()), LIMITS['panel_chars'] + 120)

    def test_command_tokens_exclude_shell_words_and_arguments(self):
        tokens = command_tokens("cd /app\nexport PATH=x\nwhich sqlite3 && sqlite3 --version\n"
                                "echo done | grep done\n/app/sqlite/bin/sqlite3 -version")
        self.assertEqual(tokens, {'which', 'sqlite3', 'grep'})
        self.assertEqual(command_tokens("bash -l -c 'which gcc && gcc --version'"), {'which', 'gcc'})
        self.assertEqual(command_tokens('which sqlite3'), {'which', 'sqlite3'})
        self.assertEqual(command_tokens('command -v sqlite3 || echo missing'), {'command', 'sqlite3'})
        self.assertEqual(command_tokens('sudo apt-get install -y gcc'), {'apt-get'})
        self.assertEqual(command_tokens("bash -l -c 'echo $PATH'"), set())

    def test_panel_budget_omits_tail_items_with_count(self):
        ledger = FailureLedger(SQLITE_TASK)
        for index in range(40):
            action, source = receipt(f't{index}', f'sqlite3 --cmd{index} ' + 'x' * 200,
                                     stdout=f'bash: line 1: sqlite3: command not found',
                                     exit_code=127)
            ledger.ingest(turn=index + 1, transition_id=f'a{index}',
                          action_batch=[action], source_events=[source])
        section = ledger.panel_section()
        body = json.loads(section.split('\n', 1)[1])
        self.assertGreater(body['omitted'], 0)
        self.assertEqual(body['omitted'] + len(body['items']), 40)
        self.assertLessEqual(len(body and json.dumps(body, ensure_ascii=False,
                                                    separators=(',', ':'))),
                             LIMITS['panel_chars'])


class EpisodeTests(unittest.TestCase):
    def make(self, *, belief_replies, consistency_replies, pma_replies):
        log = Logger()
        belief = SyncRole([json.dumps(item) for item in belief_replies])
        consistency = SyncRole(consistency_replies)
        progress = SyncRole(['{"progress": 0, "score": 0.0, "affected_record_ids": [], '
                             '"reason": "no change"}'] * 6)
        pma = AsyncRole(pma_replies)
        pos = PoSEpisode(case_id='rjc-test', config=execution_config(), logger=log,
                         belief_call=belief, consistency_call=consistency,
                         progress_call=progress, manager_class=RJCBeliefManager)
        bank = SharedViewMemoryAgent(llm=pma, memory=UniversalMemory())
        trigger = MemoryAgentTrigger(TriggerConfig(interval=1, trigger_on_first_step=True))
        episode = RJCEpisode(pos_episode=pos, memory_agent=bank, trigger=trigger, logger=log)
        return episode, belief, consistency, pma, log

    def test_manager_installs_rjc_sentinel_with_shared_flags(self):
        episode, *_ = self.make(belief_replies=[INITIAL], consistency_replies=['{"issues": []}'],
                                pma_replies=[response('', []), response('<no_intervention/>')])
        sentinel = episode.manager.sentinel
        self.assertIsInstance(sentinel, RJCSentinel)
        self.assertTrue(sentinel.shared_audit_semantics_v1)
        self.assertTrue(sentinel.shared_evidence_id_v1)
        self.assertTrue(sentinel.strict_audit_contract)

    def test_panel_shows_failure_then_pairing_and_tags_memory(self):
        pma_replies = [
            response('', []), response('<no_intervention/>'),           # reset wake
            response('', [tool('memory_save_procedural',                # wake after failure
                {'content': 'PATH issue is expected bash behavior'})]),
            response('<no_intervention/>'),
            response('', []), response('<no_intervention/>'),           # wake after closure
        ]
        episode, belief, consistency, pma, log = self.make(
            belief_replies=[INITIAL, KEEP, KEEP],
            consistency_replies=['{"issues": []}'] * 3, pma_replies=pma_replies)
        first = asyncio.run(episode.reset(task=SQLITE_TASK, observation=SQLITE_TASK, actions=[]))
        self.assertIsNone(first['ledger_section_sha256'])
        self.assertNotIn('Receipt ledger', first['panel'])

        action, source = receipt('t1', 'sqlite3 --version',
                                 stdout='bash: line 1: sqlite3: command not found', exit_code=127)
        asyncio.run(episode.update(actor_attempt=1, transition_id='actor-transition-1',
            thought='check', action_batch=[action],
            observation=json.dumps({'tool_results': [source]}), source_events=[source]))
        panel = episode.decision_panel(observation='x')
        self.assertIn('Receipt ledger', panel['panel'])
        self.assertIn('"F1"', panel['panel'])
        self.assertIn('command not found', panel['panel'])
        self.assertIn('"status":"open"', panel['panel'])
        # I5: the procedural memory written during this wake carries the open failure.
        tags = episode.memory_failure_tags
        self.assertEqual(len(tags), 1)
        self.assertEqual(list(tags.values())[0]['open_goal_relevant_failures_at_write'], ['F1'])
        bound = [row for name, row in log.rows if name == 'belief_model_input']
        self.assertTrue(any('memory_failure_tags' in json.dumps(row, ensure_ascii=False)
                            for row in bound), 'tags must reach the belief candidate input')

        action, source = receipt('t2', "bash -l -c 'which sqlite3 && sqlite3 --version'",
                                 stdout='/app/sqlite/bin/sqlite3\n3.50.4')
        asyncio.run(episode.update(actor_attempt=2, transition_id='actor-transition-2',
            thought='verify', action_batch=[action],
            observation=json.dumps({'tool_results': [source]}), source_events=[source]))
        panel = episode.decision_panel(observation='y')
        self.assertIn('"status":"closed_by_receipt"', panel['panel'])
        self.assertIn('"failing_invocation_lines":["sqlite3 --version"]', panel['panel'])
        self.assertIn("bash -l -c 'which sqlite3", panel['panel'])
        # The PMA entry keeps its write-time tag even after the receipt closure.
        self.assertEqual(list(episode.memory_failure_tags.values())[0]
                         ['open_goal_relevant_failures_at_write'], ['F1'])
        # Completion review: the gap is still open in PoS, so it fires once.
        review = episode.completion_review(turn=3)
        self.assertTrue(review['fires'])
        self.assertEqual([gap['target'] for gap in review['open_gaps']],
                         ['sqlite3 available in PATH'])
        self.assertIn('closed_by_receipt', review['prompt'])
        result = episode.get_result()
        self.assertEqual(result['method'], 'pos_pma_rjc_v0')
        self.assertEqual(result['rjc_ledger']['records'][0]['closed_by']['turn'], 2)
        # PMA and PoS role call counts are unchanged by RJC: 3 belief, 3 consistency, 6 PMA.
        self.assertEqual(len(belief.requests), 3)
        self.assertEqual(len(consistency.requests), 3)
        self.assertEqual(len(pma.requests), 6)

    def test_closure_review_attached_only_when_gap_removed_or_failure_open(self):
        episode, belief, consistency, pma, log = self.make(
            belief_replies=[INITIAL, KEEP, CLOSE],
            consistency_replies=['{"issues": []}'] * 3,
            pma_replies=[response('', []), response('<no_intervention/>')] * 3)
        asyncio.run(episode.reset(task=SQLITE_TASK, observation=SQLITE_TASK, actions=[]))
        # No failure, no removal: the consistency request carries no closure review.
        action, source = receipt('t1', 'ls /app', stdout='vendor')
        asyncio.run(episode.update(actor_attempt=1, transition_id='a1', thought='look',
            action_batch=[action], observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertFalse(any('closure review' in m['content'] for m in consistency.requests[-1]))
        # Gap removed: the review names the removed gap; the ledger has no open failures.
        action, source = receipt('t2', 'ln -s /app/sqlite/bin/sqlite3 /usr/local/bin/sqlite3 && '
                                 'which sqlite3', stdout='/usr/local/bin/sqlite3')
        asyncio.run(episode.update(actor_attempt=2, transition_id='a2', thought='link',
            action_batch=[action], observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        last = consistency.requests[-1]
        reviews = [m for m in last if 'closure review' in m['content']]
        self.assertEqual(len(reviews), 1)
        body = json.loads(reviews[0]['content'].split('\n', 1)[1])
        self.assertEqual(body['removed_gaps'], ['sqlite3 available in PATH'])
        self.assertEqual(body['items'], [])
        self.assertEqual(episode.manager.sentinel.closure_review, None)
        logged = [row for name, row in log.rows if name == 'rjc_closure_review_input']
        self.assertEqual(len(logged), 1)
        self.assertEqual(logged[0]['removed_gaps'], ['sqlite3 available in PATH'])
        review = episode.completion_review(turn=3)
        self.assertFalse(review['fires'])

    def test_irrelevant_failure_does_not_fire_or_tag(self):
        episode, *_ , log = self.make(
            belief_replies=[INITIAL, CLOSE], consistency_replies=['{"issues": []}'] * 2,
            pma_replies=[response('', []), response('<no_intervention/>'),
                         response('', [tool('memory_save_knowledge', {'content': 'file missing'})]),
                         response('<no_intervention/>')])
        asyncio.run(episode.reset(task=SQLITE_TASK, observation=SQLITE_TASK, actions=[]))
        action, source = receipt('t1', 'file /app/x', stdout='bash: line 1: file: command not found',
                                 exit_code=127)
        asyncio.run(episode.update(actor_attempt=1, transition_id='a1', thought='probe',
            action_batch=[action], observation=json.dumps({'tool_results': [source]}),
            source_events=[source]))
        self.assertEqual(episode.ledger.open_records(goal_relevant_only=False)[0]['tokens'], ['file'])
        self.assertEqual(episode.ledger.tag_for_now(), [])
        self.assertEqual(list(episode.memory_failure_tags.values())[0]
                         ['open_goal_relevant_failures_at_write'], [])
        self.assertNotIn('Receipt ledger', episode.decision_panel(observation='z')['panel'])
        self.assertFalse(episode.completion_review(turn=2)['fires'])


if __name__ == '__main__':
    unittest.main()
