"""Actual installed LiteLLM -> loopback HTTP, with no provider API request."""
import asyncio
import http.server
import json
import os
from pathlib import Path
import threading
import unittest

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
from harbor.llms.lite_llm import LiteLLM
from pma_native_support import original_config
from pma_native_support import gateway_config
from isolated_transport import resolve_request

REFERENCE = Path(__file__).resolve().parents[1] / 'some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent'


class WireTests(unittest.TestCase):
    def test_both_models_use_messages_and_preserve_temperature_and_tools(self):
        requests = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, body))
                blocks = ([{'type': 'tool_use', 'id': 'toolu_fixture',
                            'name': 'fixture_lookup', 'input': {'query': 'test'}}]
                          if body.get('tools') else [{'type': 'text', 'text': 'fixture answer'}])
                response = json.dumps({'id': 'msg_fixture', 'type': 'message',
                    'role': 'assistant', 'model': body['model'], 'content': blocks,
                    'stop_reason': 'tool_use' if body.get('tools') else 'end_turn',
                    'stop_sequence': None, 'usage': {'input_tokens': 12, 'output_tokens': 7}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response)))
                self.end_headers()
                self.wfile.write(response)
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            config = original_config(REFERENCE, port=server.server_port)
            for side in (config.model, config.memory):
                client = LiteLLM(model_name=side.model_name, api_base=side.api_base,
                                 api_key=side.api_key, temperature=side.temperature)
                kwargs = {'prompt': 'public fixture', 'system_prompt': 'fixture system'}
                if side is config.memory:
                    kwargs['tools'] = [{'type': 'function', 'function': {
                        'name': 'fixture_lookup', 'description': 'fixture',
                        'parameters': {'type': 'object', 'properties': {
                            'query': {'type': 'string'}}, 'required': ['query']}}}]
                result = asyncio.run(client.call(**kwargs))
                self.assertIsNotNone(result.usage)
                if side is config.memory:
                    self.assertEqual(result.tool_calls[0].function.name, 'fixture_lookup')
                else:
                    self.assertEqual(result.content, 'fixture answer')
            self.assertEqual(len(requests), 2)
            for request, side in zip(requests, (config.model, config.memory)):
                self.assertEqual(request[0].split('?')[0], '/v1/messages')
                self.assertEqual(request[1]['temperature'], side.temperature)
                self.assertEqual(request[1]['model'], side.model_name.removeprefix('anthropic/'))
                target, headers, payload = resolve_request(request[0],
                    json.dumps(request[1]).encode(), gateway_config('https://example.invalid', 'fixture'))
                self.assertTrue(target.startswith('https://example.invalid/v1/messages'))
                self.assertEqual(json.loads(payload)['model'], request[1]['model'])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
