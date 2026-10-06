"""Fresh one-decision calls for the frozen panel; execution requires external authorization.

Importing or auditing this module never imports a provider, reads sealed gold,
or opens a network connection. No execution authorization is shipped here.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlsplit

from preview_runner import PANEL, assemble, load_inputs
from stage1_plan import (EXPECTED_MODEL, FIXTURE_COMMIT, PROFILE, canonical,
                         frozen_fixture_manifest, generate_plan, sha)


REPO = PANEL.parents[1]
PLAN = PANEL / 'stage1' / 'PLAN.json'


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2,
                                default=str).encode('utf-8') + b'\n')


def validate_plan(repo=REPO, panel=PANEL, plan_path=PLAN):
    manifest = frozen_fixture_manifest(repo, panel)
    expected = generate_plan(manifest)
    actual = json.loads(plan_path.read_bytes())
    if actual != expected or actual['execution_authorized'] is not False:
        raise ValueError('Stage 1 allocation differs from committed deterministic plan')
    if len(actual['trials']) != 54 or len({r['trial_id'] for r in actual['trials']}) != 54:
        raise ValueError('Stage 1 must have 54 unique logical decisions')
    return actual


def semantic_request(trial, panel=PANEL):
    packet, shell, core = load_inputs(trial['case_id'], trial['condition'], panel)
    request = assemble(packet, shell, core)
    if trial['frame'] != packet['frame']:
        raise ValueError('Trial frame differs from packet')
    raw = canonical(request)
    request_hash = sha(raw)
    if request_hash != trial['request_sha256']:
        raise ValueError('Assembled semantic request differs from frozen trial identity')
    return request, raw, request_hash


def parse_action(blocks, frame):
    """Parse one provider response, without repair or any further model turn."""
    calls = [block for block in blocks if block.get('type') == 'tool_use']
    if len(calls) != 1:
        return {'selected_action': 'invalid', 'invalid_reason': 'control_tool_call_count',
                'tool_call_count': len(calls), 'intervention_message': None}
    call = calls[0]
    name, args = call.get('name'), call.get('input')
    valid_names = {'wait', 'intervene'} | ({'allow_complete'} if frame == 'root' else set())
    if name not in valid_names:
        reason = 'unknown_or_disallowed_tool'
    elif not isinstance(args, dict):
        reason = 'arguments_not_object'
    elif name == 'intervene' and (set(args) != {'message'} or not isinstance(args['message'], str)):
        reason = 'intervention_schema_mismatch'
    elif name in {'wait', 'allow_complete'} and args:
        reason = 'control_schema_mismatch'
    else:
        return {'selected_action': name, 'invalid_reason': None, 'tool_call_count': 1,
                'intervention_message': args['message'] if name == 'intervene' else None}
    return {'selected_action': 'invalid', 'invalid_reason': reason,
            'tool_call_count': 1, 'intervention_message': None}


def safe_effective_profile(profile_name, raw, client, raw_sha):
    """Archive exact effective public model parameters and the private config hash, never secrets."""
    parsed = urlsplit(client.api_base)
    return {'profile': profile_name, 'private_profile_file_sha256': raw_sha,
            'provider': client.provider, 'api_mode': client.api_mode, 'model': client.model,
            'temperature': client.temperature, 'thinking_type': client.thinking_type,
            'reasoning_effort': client.reasoning_effort, 'max_tokens': client.max_tokens,
            'context_window': client.context_window,
            'connect_timeout': client.connect_timeout, 'read_timeout': client.read_timeout,
            'max_retries': client.max_retries, 'verify': client.verify,
            'transport_route': raw.get('transport_route'),
            'api_base_host': parsed.hostname,
            'api_base_sha256': sha(client.api_base.encode('utf-8')),
            'proxy_present': bool(raw.get('proxy'))}


def load_private_profile(config_path: Path):
    raw_file = config_path.read_bytes()
    profiles = json.loads(raw_file)
    if PROFILE not in profiles or not isinstance(profiles[PROFILE], dict):
        raise ValueError('Frozen Monitor profile is missing')
    raw = profiles[PROFILE]
    if raw.get('model') != EXPECTED_MODEL:
        raise ValueError('Configured model differs from expected model identity')
    if not raw.get('apikey') or not raw.get('apibase'):
        raise ValueError('Private provider configuration is incomplete')
    return raw, sha(raw_file)


def require_authorization(path: Path, plan_path: Path, profile_config: Path):
    """Independent, absent-by-default authority; no valid file is created this turn."""
    record = json.loads(path.read_bytes())
    required = {'execution_authorized': True, 'fixture_commit': FIXTURE_COMMIT,
                'plan_sha256': sha(plan_path.read_bytes()),
                'runner_sha256': sha(Path(__file__).read_bytes()),
                'private_profile_file_sha256': sha(profile_config.read_bytes()),
                'approved_logical_calls': 54}
    if any(record.get(key) != value for key, value in required.items()):
        raise ValueError('Independent Stage 1 authorization is absent or mismatched')
    return {key: record[key] for key in required}


def real_transport(request, profile, profile_file_sha, before_send=None):
    """Use one fresh existing Monitor provider client and its configured transport retries.

    SSE line bytes are archived per attempt. The adapter asserts every retry
    constructs the same provider payload. It does not add recovery prompts.
    """
    sys.path.insert(0, str(REPO / 'GenericAgent-main'))
    import requests
    from monitor_agent_core.provider import MonitorProviderClient, RetryableProviderError

    class CaptureClient(MonitorProviderClient):
        def __init__(self, name, config):
            super().__init__(name, config)
            self.attempt_payload_hashes = []
            self.raw_streams = []
            self.provider_observed_model = None

        def _request_once(self, tools):
            if self.provider != 'anthropic':
                raise ValueError('Stage 1 frozen profile requires Anthropic Messages transport')
            _, _, payload = self._anthropic_request(tools)
            payload_hash = sha(canonical(payload))
            if self.attempt_payload_hashes and payload_hash != self.attempt_payload_hashes[0]:
                raise ValueError('Transport retry changed provider request payload')
            self.attempt_payload_hashes.append(payload_hash)
            self.raw_streams.append([])
            return super()._request_once(tools)

        def _progress_lines(self, lines):
            for line in super()._progress_lines(lines):
                raw = line if isinstance(line, bytes) else str(line).encode('utf-8')
                self.raw_streams[-1].append(base64.b64encode(raw).decode('ascii'))
                if raw.startswith(b'data:'):
                    try:
                        event = json.loads(raw[5:].strip())
                        if event.get('type') == 'message_start':
                            observed = (event.get('message') or {}).get('model')
                            if observed:
                                self.provider_observed_model = str(observed)
                    except (ValueError, TypeError, AttributeError):
                        pass
                yield line

    client = CaptureClient(PROFILE, dict(profile))
    if client.model != EXPECTED_MODEL or client.provider != 'anthropic':
        raise ValueError('Actual provider/model differs from frozen Stage 1 identity')
    client.system = request['system']
    client.history = [{'role': 'user', 'content': [
        {'type': 'text', 'text': request['messages'][0]['content']}]}]
    _, _, payload = client._anthropic_request(request['tools'])
    effective = safe_effective_profile(PROFILE, profile, client, profile_file_sha)
    if before_send is not None:
        before_send(payload, effective)
    blocks, usage, error = None, None, None
    retryable = (RetryableProviderError, requests.Timeout, requests.ConnectionError,
                 requests.exceptions.ChunkedEncodingError)
    for attempt in range(client.max_retries + 1):
        started = time.monotonic()
        started_at = time.time()
        client.last_response_metadata = {}
        client._progress_request_id = uuid.uuid4().hex
        try:
            # A complete response, including one with zero control calls, is
            # returned once and later marked invalid. It is never format-retried.
            blocks, usage = client._request_once(request['tools'])
            client.request_attempts.append({'attempt': attempt + 1, 'started_at': started_at,
                'outcome': 'response',
                'duration_seconds': time.monotonic() - started})
            break
        except retryable as exc:
            client.request_attempts.append({'attempt': attempt + 1, 'started_at': started_at,
                'outcome': 'retryable_transport_or_incomplete_response',
                'error_type': type(exc).__name__,
                'duration_seconds': time.monotonic() - started})
            if attempt == client.max_retries:
                error = {'type': type(exc).__name__,
                         'message': str(exc).replace(client.api_key, '[REDACTED]')}
                break
            time.sleep(min(8, 1.5 * (2 ** attempt)))
        except Exception as exc:
            client.request_attempts.append({'attempt': attempt + 1, 'started_at': started_at,
                'outcome': 'terminal_error',
                'error_type': type(exc).__name__,
                'duration_seconds': time.monotonic() - started})
            error = {'type': type(exc).__name__,
                     'message': str(exc).replace(client.api_key, '[REDACTED]')}
            break
    raw_stream = {'encoding': 'base64_of_each_iter_lines_byte_string',
                  'delimiter_note': 'Original HTTP line delimiters are not retained by iter_lines',
                  'attempts': client.raw_streams}
    return {'blocks': blocks, 'usage': usage, 'error': error,
            'response_metadata': client.last_response_metadata,
            'request_attempts': client.request_attempts,
            'provider_observed_model': client.provider_observed_model,
            'provider_payload': payload,
            'attempt_payload_sha256': client.attempt_payload_hashes,
            'raw_response_stream': raw_stream, 'effective_profile': effective}


def run_authorized(plan_path: Path, profile_config: Path, authorization: Path, output_root: Path):
    plan = validate_plan(plan_path=plan_path)
    auth = require_authorization(authorization, plan_path, profile_config)
    profile, profile_file_sha = load_private_profile(profile_config)
    if output_root.exists():
        raise ValueError('Stage 1 output root must be unused; no automatic resume or rerun')
    output_root.mkdir(parents=True)
    write_json(output_root / 'run_identity.json', {'fixture_commit': FIXTURE_COMMIT,
        'plan_sha256': sha(plan_path.read_bytes()), 'authorization_identity': auth,
        'profile_file_sha256': profile_file_sha})
    for trial in plan['trials']:
        trial_dir = output_root / f"{trial['ordinal']:02d}_{trial['trial_id']}"
        trial_dir.mkdir()
        request, raw_request, request_hash = semantic_request(trial)
        (trial_dir / 'request.json').write_bytes(raw_request)
        def archive_pre_send(payload, effective):
            write_json(trial_dir / 'provider_payload.json', payload)
            write_json(trial_dir / 'effective_profile.json', effective)
        result = real_transport(request, profile, profile_file_sha, archive_pre_send)
        write_json(trial_dir / 'raw_response_stream.json', result['raw_response_stream'])
        record = {**trial, 'request_sha256': request_hash,
                  'packet_sha256': trial['packet_sha256'],
                  'shell_sha256': trial['shell_sha256'],
                  'cognitive_core_sha256': trial['cognitive_core_sha256'],
                  'provider_payload_sha256': sha(canonical(result['provider_payload'])),
                  'raw_response_sha256': sha((trial_dir / 'raw_response_stream.json').read_bytes()),
                  'provider_response_id': result['response_metadata'].get('provider_message_id'),
                  'provider_observed_model': result['provider_observed_model'],
                  'stop_reason': result['response_metadata'].get('stop_reason'),
                  'usage': result['usage'], 'request_attempts': result['request_attempts'],
                  'attempt_payload_sha256': result['attempt_payload_sha256'],
                  'effective_profile': result['effective_profile'],
                  'raw_response_blocks': result['blocks'],
                  'selected_tool_calls': [block for block in result['blocks'] or []
                                          if block.get('type') == 'tool_use'],
                  'transport_error': result['error']}
        if result['error'] is None:
            record.update(parse_action(result['blocks'] or [], trial['frame']))
            record['status'] = 'response_recorded'
        else:
            record.update(selected_action=None, invalid_reason=None,
                          intervention_message=None, status='transport_failure')
        if result['provider_observed_model'] not in (None, EXPECTED_MODEL):
            record['status'] = 'model_identity_mismatch'
        write_json(trial_dir / 'record.json', record)
        if result['provider_observed_model'] not in (None, EXPECTED_MODEL):
            raise RuntimeError('Provider returned a different model identity; Stage 1 halted')
        if result['error'] is not None:
            raise RuntimeError('Transport/provider failure archived; Stage 1 halted without replacement')


def main():
    parser = argparse.ArgumentParser(description='Stage 1; defaults to zero-network identity audit')
    parser.add_argument('--plan', type=Path, default=PLAN)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--profile-config', type=Path)
    parser.add_argument('--output-root', type=Path)
    args = parser.parse_args()
    if not args.run:
        plan = validate_plan(plan_path=args.plan.resolve())
        print(json.dumps({'status': 'offline_identity_audit_only',
                          'planned_logical_calls': len(plan['trials']),
                          'fixture_commit': FIXTURE_COMMIT}))
        return
    if not all((args.authorization, args.profile_config, args.output_root)):
        parser.error('--run requires --authorization, --profile-config and --output-root')
    run_authorized(args.plan.resolve(), args.profile_config.resolve(),
                   args.authorization.resolve(), args.output_root.resolve())


if __name__ == '__main__':
    main()
