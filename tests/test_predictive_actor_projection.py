"""Compare the predictive observer projection to native GA request assembly."""
import ast
import copy
import json
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'GenericAgent-main/llmcore.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))


def node(name, kind=ast.FunctionDef):
    return next(item for item in TREE.body if isinstance(item, kind) and item.name == name)


class Backend:
    def __init__(self, history=None):
        self.history = [{'role': 'user'}] if history is None else history
        self.model = 'fixture'
        self.received = []

    def ask(self, message):
        self.received.append(copy.deepcopy(message))
        if False:
            yield None
        return None


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        scope = {'copy': copy, 'json': json,
                 '_write_llm_log': lambda *args, **kwargs: None}
        body = [node('_native_user_content'), node('_public_response_blocks'),
                node('NativeToolClient', ast.ClassDef)]
        exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])),
                     str(SOURCE), 'exec'), scope)
        self.scope = scope

    def test_native_request_parity_and_missing_results(self):
        cases = [
            ([{'type': 'text', 'text': 'framework context'}],
             [{'tool_use_id': 'a', 'content': 'output'}], ['a']),
            ([{'type': 'text', 'text': '  '}, {'type': 'text', 'text': 'x'}],
             [{'tool_use_id': '', 'content': 'no id'},
              {'tool_use_id': 'b', 'content': 'B'}], ['a', 'b']),
            ([{'type': 'text', 'text': 'working memory\nround prompt'}], [], []),
            ([], [], []),
        ]
        for content, results, pending in cases:
            with self.subTest(content=content, results=results):
                backend = Backend()
                client = self.scope['NativeToolClient'].__new__(
                    self.scope['NativeToolClient'])
                client.backend = backend
                client._pending_tool_ids = list(pending)
                client.log_path = False
                expected = self.scope['_native_user_content'](content, results, pending)
                generator = client.chat([{'role': 'user', 'content': copy.deepcopy(content),
                                          'tool_results': copy.deepcopy(results)}])
                try:
                    while True:
                        next(generator)
                except StopIteration:
                    pass
                self.assertEqual(backend.received[0]['content'], expected)

    def test_stale_pending_id_dropped_when_history_empty(self):
        backend = Backend(history=[])
        client = self.scope['NativeToolClient'].__new__(self.scope['NativeToolClient'])
        client.backend, client._pending_tool_ids, client.log_path = backend, ['stale'], False
        generator = client.chat([{'role': 'user', 'content': 'new task'}])
        try:
            while True:
                next(generator)
        except StopIteration:
            pass
        self.assertEqual(backend.received[0]['content'],
                         self.scope['_native_user_content'](
                             [{'type': 'text', 'text': 'new task'}], [], []))

    def test_private_blocks_removed_without_changing_public_order(self):
        blocks = [{'type': 'text', 'text': 'before'},
                  {'type': 'thinking', 'thinking': 'private marker'},
                  {'type': 'tool_use', 'id': 'x', 'name': 'shell',
                   'input': {'cmd': 'echo ok'}},
                  {'type': 'text', 'text': 'after'}]
        projected = self.scope['_public_response_blocks'](blocks)
        self.assertEqual([item['type'] for item in projected],
                         ['text', 'tool_use', 'text'])
        self.assertNotIn('private marker', str(projected))
        self.assertIsNone(self.scope['_public_response_blocks'](
            [{'type': 'unsupported', 'body': 'unknown'}]))


if __name__ == '__main__':
    unittest.main()
