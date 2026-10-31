"""Shared request path for scriptable fakes and existing PMA llm.call clients."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys

from .inputs import D, require
from .citation_inputs import identity
from .private_faults import record_failure


def durable(path, row):
    """Adapted candidate_transport_worker._durable; never serialize client/profile."""
    with Path(path).open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


class FakeClient:
    """No network imports. Responses supplied by tests, never evidence inference."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    async def call(self, *, prompt, system, tools=None):
        self.calls.append({'prompt': prompt, 'system': system, 'tools': tools})
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        return type('Response', (), {'content': value, 'tool_calls': []})()


class ResponseProtocolError(ValueError):
    """Received a response, but it violates the text-only reviewer protocol."""
    def __init__(self, code, raw_response=None):
        super().__init__(code)
        self.code = code
        self.raw_response = raw_response


class CapturedTransport:
    def __init__(self, client, directory=None, *, fake=False):
        self.client, self.fake = client, fake
        self.directory = Path(directory) if directory else None
        self.records = []
        self.calls = 0
        self.audit_failure = None

    def _durable(self, path, row):
        try:
            durable(path, row)
        except Exception as error:
            self.audit_failure = record_failure(self.directory, error)
            raise

    async def send(self, request):
        # This exact payload is used by fake and real clients alike.
        require(request.get('tools') is None, 'review_tools_forbidden')
        payload = {k: request[k] for k in ('prompt', 'system', 'tools')}
        self.calls += 1
        row = {'call_index': self.calls, 'phase': request['phase'],
               'request': copy.deepcopy(payload), 'fake': self.fake,
               'audit_request_sha256': request.get('audit_request_sha256'),
               'evidence_policy': request.get('evidence_policy'),
               'effective_system_sha256': hashlib.sha256(payload['system'].encode('utf-8')).hexdigest(),
               'effective_prompt_sha256': hashlib.sha256(payload['prompt'].encode('utf-8')).hexdigest(),
               'effective_payload_sha256': identity(payload),
               'operation_kind': request.get('operation_kind', request.get('audit_operation_kind'))}
        for key in ('review_strategy', 'op_index', 'focus_id', 'claim_index', 'submitted_evidence_sha256', 'operation_kind'):
            if key in request:
                row[key] = request[key]
        self.records.append(row)
        if self.directory:
            self._durable(self.directory / 'requests.jsonl', row)
        try:
            response = await self.client.call(**payload)
            content = getattr(response, 'content', None)
            raw = content if isinstance(content, str) else None
            row['response'] = raw
            if request.get('review_strategy') in ('claim-split-same-evidence-v1', 'claim-split-same-evidence-v2', 'claim-split-same-evidence-v3', 'claim-split-same-evidence-v4'):
                finish = getattr(response, 'finish_reason', None)
                if finish is not None:
                    row['finish_reason'] = finish
                if finish in ('length', 'max_tokens', 'max_output_tokens'):
                    raise ResponseProtocolError('truncated_response', raw)
            if getattr(response, 'tool_calls', None):
                raise ResponseProtocolError('unexpected_tool_calls', raw)
            if raw is None:
                raise ResponseProtocolError('response_content_type')
            row.update(response=content, status='returned')
            return content
        except ResponseProtocolError as error:
            row.update(status='protocol_error', protocol_error=error.code,
                       error_type=type(error).__name__)
            raise
        except Exception as error:
            row.update(status='call_error', error_type=type(error).__name__)
            raise
        finally:
            if self.directory:
                self._durable(self.directory / 'responses.jsonl', {k: v for k, v in row.items()
                    if k != 'request'})


def load_profile_client(repo, profile_path, profile_key, workdir, *, authorized=False):
    """Explicit future execution route; no credentials read until authorization flag.

    Reuses pinned construct_upstream and its profile adapter, then only _memory_llm.
    No process(), Task, maintenance, judgment or evaluator is invoked.
    """
    require(authorized, 'real_execution_requires_explicit_authorization')
    root = Path(repo).resolve() / D
    vendor = root / 'vendor' / 'pma_89e5c0d'
    for path in (root, vendor / 'src', vendor / 'external' / 'harbor' / 'src'):
        sys.path.insert(0, str(path))
    from episode import construct_upstream
    profile = json.loads(Path(profile_path).read_text(encoding='utf-8'))[profile_key]
    agent = construct_upstream(Path(workdir), memory_profile=profile)
    return agent._memory_llm
