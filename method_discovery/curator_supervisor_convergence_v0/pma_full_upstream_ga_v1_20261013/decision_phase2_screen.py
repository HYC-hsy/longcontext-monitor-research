"""Six-input U/V1/D1 archived Phase-2 comparison; live requires one-use approval.

This reuses the original recorded prompt, not historical memory or a new Task
process. Labels remain in the host manifest and never enter the model prompt.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
from importlib.metadata import version
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid

import litellm

from harbor.llms.base import LLMResponse
from harbor.llms.lite_llm import LiteLLM
from memory_agent.memory.memory_agent import PHASE2_SYSTEM
from memory_agent.memory.memory_agent import MemoryAgent
from memory_agent.memory.universal_memory import UniversalMemory
from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2

from decision_reminder_agent import phase2_prompt, phase2_system
from decision_phase2_views import project
from episode import construct_upstream
from static_source_live import profile_identity, public_value
from worker_main import PMAAuditIntegrityError, append_private_audit, install_transport_audit


HERE = Path(__file__).resolve().parent
PUBLIC = HERE / 'generic_single_run_20261015/real_12_r1_public_20261016'
CASES = (('07', 235), ('14', 85), ('14', 105), ('22', 7),
         ('07', 161), ('18', 6))
VARIANTS = ('U', 'V1', 'D1')
LIVE_SCHEMA = 'pma-decision-phase2-once-v1'
VIEW_SCHEMA = 'pma-decision-phase2-input-views-once-v2'
VIEW_DRAFT_SCHEMA = 'pma-decision-phase2-input-views-draft-v2'
PROFILE_SHA256 = 'cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1'
CODE_FILES = ('decision_phase2_screen.py', 'decision_phase2_views.py',
              'decision_reminder_agent.py',
              'episode.py', 'worker_main.py', 'static_source_live.py',
              'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py',
              'vendor/pma_89e5c0d/src/memory_agent/memory/universal_memory.py',
              'vendor/pma_89e5c0d/src/memory_agent/memory/memory_agent.py',
              'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/lite_llm.py')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def append_json(path: Path, row: dict) -> None:
    append_private_audit(path, row)


def write_new(path: Path, row: dict) -> None:
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(row, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def code_commit() -> str:
    result = subprocess.run(('git', 'rev-parse', 'HEAD'), cwd=HERE,
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def code_identity() -> dict:
    paths = [str(HERE / name) for name in CODE_FILES]
    for staged in (False, True):
        command = ['git', 'diff', '--quiet']
        if staged:
            command.append('--cached')
        command += ['--', *paths]
        if subprocess.run(command, cwd=HERE, check=False).returncode:
            raise PermissionError('tracked Phase-2 execution code is not clean')
    expected_modules = (
        (MemoryAgent, 'vendor/pma_89e5c0d/src/memory_agent/memory/memory_agent.py'),
        (UniversalMemory, 'vendor/pma_89e5c0d/src/memory_agent/memory/universal_memory.py'),
        (MemoryEnabledTerminus2, 'vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py'),
        (LiteLLM, 'vendor/pma_89e5c0d/external/harbor/src/harbor/llms/lite_llm.py'))
    if any(Path(inspect.getfile(obj)).resolve() != (HERE / name).resolve()
           for obj, name in expected_modules):
        raise PermissionError('loaded PMA/Harbor modules differ from frozen vendor')
    return {'commit': code_commit(),
            'files': {name: sha((HERE / name).read_bytes()) for name in CODE_FILES},
            'dependencies': {name: version(name) for name in
                             ('litellm', 'tenacity', 'pydantic')}}


def checked_profile(path: Path) -> tuple[dict, dict]:
    if sha(path.read_bytes()) != PROFILE_SHA256:
        raise PermissionError('PMA private profile bytes differ from approved Opus 4.8 profile')
    profile, safe = profile_identity(path)
    safe['effective_timeout'] = profile['read_timeout']
    safe['effective_upstream_retry_attempts'] = 3
    safe['profile_file_sha256'] = PROFILE_SHA256
    return profile, safe


def read_case(arm: str, step: int) -> dict:
    path = PUBLIC / arm / 'pma_requests_public.json'
    raw = path.read_bytes()
    rows = json.loads(raw)
    index = 2 * step - 1
    if index >= len(rows):
        raise RuntimeError('archived PMA step missing')
    selected = rows[index]
    if (selected.get('phase') != 'context_decision' or
            selected.get('system') != PHASE2_SYSTEM or
            selected.get('tools') is not None or
            not selected.get('prompt', '').startswith(f'## Step {step}\n')):
        raise RuntimeError('archived original Phase 2 identity mismatch')
    return {'source_path': path.relative_to(HERE).as_posix(),
            'source_file_sha256': sha(raw), 'prompt': selected['prompt'],
            'prompt_sha256': sha(selected['prompt'].encode('utf-8')),
            'system_sha256': sha(selected['system'].encode('utf-8')),
            'archive_index': index}


def requests() -> list[dict]:
    rows = []
    for arm, step in CASES:
        archive = read_case(arm, step)
        for variant in VARIANTS:
            prompt = (archive['prompt'] if variant == 'U' else
                      phase2_prompt(archive['prompt'], variant))
            system = PHASE2_SYSTEM if variant == 'U' else phase2_system(variant)
            rows.append({'arm': arm, 'pma_step': step, 'variant': variant,
                         'source_path': archive['source_path'],
                         'source_file_sha256': archive['source_file_sha256'],
                         'archive_index': archive['archive_index'],
                         'original_prompt_sha256': archive['prompt_sha256'],
                         'original_system_sha256': archive['system_sha256'],
                         'request_prompt_sha256': sha(prompt.encode('utf-8')),
                         'request_system_sha256': sha(system.encode('utf-8')),
                         'tools': None})
    return rows


def view_requests() -> list[dict]:
    rows = []
    rotations = (('F', 'EB', 'E'), ('EB', 'E', 'F'), ('E', 'F', 'EB'))
    for arm, step in CASES:
        archive = read_case(arm, step)
        full = phase2_prompt(archive['prompt'], 'D1')
        for occurrence, rotation in enumerate(rotations, 1):
            for view in rotation:
                visible, identity = project(full, view)
                rows.append({'arm': arm, 'pma_step': step, 'variant': 'D1',
                             'input_view': view, 'occurrence': occurrence,
                             'run_id': f'case-{arm}-{step}-r{occurrence}-{view.lower()}',
                             'source_path': archive['source_path'],
                             'source_file_sha256': archive['source_file_sha256'],
                             'archive_index': archive['archive_index'],
                             'original_prompt_sha256': archive['prompt_sha256'],
                             'original_system_sha256': archive['system_sha256'],
                             'request_prompt_sha256': sha(visible.encode('utf-8')),
                             'request_system_sha256': sha(phase2_system('D1').encode('utf-8')),
                             'projection_identity_sha256': sha(json.dumps(identity,
                                 ensure_ascii=False, sort_keys=True).encode('utf-8')),
                             'step_count': identity['step_count'], 'tools': None})
    if len(rows) != 54 or sum(row['step_count'] for row in rows[::9]) != 43:
        raise RuntimeError('fixed archived input-view asset count mismatch')
    if len({row['run_id'] for row in rows}) != len(rows):
        raise RuntimeError('duplicate run identity')
    return rows


def planned(schema: str) -> list[dict]:
    if schema in (LIVE_SCHEMA, 'pma-decision-phase2-screen-draft-v1'):
        return requests()
    if schema in (VIEW_SCHEMA, VIEW_DRAFT_SCHEMA):
        return view_requests()
    raise ValueError('unknown Phase-2 plan schema')


def slot_name(row: dict, number: int, schema: str) -> str:
    if schema == VIEW_SCHEMA:
        run_id = row['run_id']
        if not re.fullmatch(r'case-\d+-\d+-r[1-3]-(?:f|eb|e)', run_id):
            raise PermissionError('unsafe Phase-2 run identity')
        return f'{number:02d}-{run_id}'
    return f'{number:02d}-{row["variant"].lower()}'


def request_for(row: dict) -> tuple[str, str, dict | None]:
    source = read_case(row['arm'], row['pma_step'])
    variant = row['variant']
    full = (source['prompt'] if variant == 'U' else
            phase2_prompt(source['prompt'], variant))
    identity = None
    if 'input_view' in row:
        if variant != 'D1':
            raise PermissionError('input views require D1')
        full, identity = project(full, row['input_view'])
        if (sha(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode('utf-8'))
                != row['projection_identity_sha256'] or
                identity['step_count'] != row['step_count']):
            raise PermissionError('projected field identity changed')
    system = PHASE2_SYSTEM if variant == 'U' else phase2_system(variant)
    if (sha(full.encode('utf-8')) != row['request_prompt_sha256'] or
            sha(system.encode('utf-8')) != row['request_system_sha256'] or
            row['source_file_sha256'] != source['source_file_sha256']):
        raise PermissionError('archived Phase-2 request identity changed')
    return full, system, identity


def prepare(output: Path, *, input_views: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    schema = VIEW_DRAFT_SCHEMA if input_views else 'pma-decision-phase2-screen-draft-v1'
    manifest = {'schema': schema,
                'execution_authorized': False,
                'scope': 'six_archived_Phase2_inputs_only_no_Task_no_Phase1',
                'planned_order': planned(schema)}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2),
                                          encoding='utf-8')
    return {'requests': len(manifest['planned_order']),
            'execution_authorized': False,
            'manifest_sha256': sha((output / 'manifest.json').read_bytes())}


def freeze(manifest_path: Path, output: Path, profile_path: Path,
           *, input_views: bool = False) -> dict:
    if manifest_path.exists() or output.exists():
        raise FileExistsError('new manifest and output root are required')
    _, safe_profile = checked_profile(profile_path)
    identity = code_identity()
    schema = VIEW_SCHEMA if input_views else LIVE_SCHEMA
    order = planned(schema)
    manifest = {'schema': schema, 'execution_authorized': False,
                'batch_id': 'd1v1-' + uuid.uuid4().hex[:20],
                'code_identity': identity, 'profile_public': safe_profile,
                'profile_sha256': PROFILE_SHA256,
                'output_root': str(output.resolve()),
                'planned_order': order,
                'logical_requests': len(order),
                'request_timeout_seconds': safe_profile['effective_timeout'],
                'upstream_retry_attempts': 3,
                'inner_network_attempts': 'unknown',
                'scope': 'archived_public_Phase2_only_no_Task_no_Phase1'}
    if len({row.get('run_id', str(index)) for index, row in enumerate(order)}) != len(order):
        raise RuntimeError('duplicate planned run identity')
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    write_new(manifest_path, manifest)
    return {'batch_id': manifest['batch_id'],
            'manifest_sha256': sha(manifest_path.read_bytes()),
            'code_commit': identity['commit'], 'execution_authorized': False,
            'profile_public': safe_profile}


def check_frozen(manifest_path: Path, profile_path: Path) -> tuple[dict, dict]:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    profile, safe_profile = checked_profile(profile_path)
    try:
        current_requests = planned(manifest.get('schema'))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        raise PermissionError('archived Phase-2 source or prompt identity invalid') from exc
    if (manifest.get('schema') not in (LIVE_SCHEMA, VIEW_SCHEMA) or
            manifest.get('execution_authorized') is not False or
            manifest.get('code_identity') != code_identity() or
            manifest.get('profile_public') != safe_profile or
            manifest.get('profile_sha256') != PROFILE_SHA256 or
            manifest.get('planned_order') != current_requests or
            manifest.get('logical_requests') != len(current_requests) or
            manifest.get('request_timeout_seconds') != profile['read_timeout'] or
            manifest.get('upstream_retry_attempts') != 3 or
            not isinstance(manifest.get('batch_id'), str) or
            not isinstance(manifest.get('output_root'), str) or
            Path(manifest['output_root']).exists()):
        raise PermissionError('frozen Phase-2 code/profile/source/order identity mismatch')
    return manifest, profile


def authorize(manifest_path: Path, auth_path: Path, profile_path: Path,
              authorization_source: str) -> dict:
    if auth_path.exists() or not authorization_source.strip():
        raise PermissionError('new one-use approval and source are required')
    manifest, _ = check_frozen(manifest_path, profile_path)
    auth = {'schema': manifest['schema'] + '-authorization',
            'execution_authorized': True,
            'authorization_source': authorization_source,
            'batch_id': manifest['batch_id'],
            'manifest_sha256': sha(manifest_path.read_bytes()),
            'code_identity': manifest['code_identity'],
            'profile_sha256': PROFILE_SHA256,
            'output_root': manifest['output_root'],
            'planned_order': manifest['planned_order'],
            'issued_epoch': time.time()}
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    write_new(auth_path, auth)
    return {'batch_id': manifest['batch_id'],
            'authorization_sha256': sha(auth_path.read_bytes()),
            'authorized_requests': len(auth['planned_order'])}


def check_authorized(manifest_path: Path, auth_path: Path,
                     profile_path: Path) -> tuple[dict, dict, dict]:
    manifest, profile = check_frozen(manifest_path, profile_path)
    auth = json.loads(auth_path.read_text(encoding='utf-8'))
    if (auth.get('schema') != manifest['schema'] + '-authorization' or
            auth.get('execution_authorized') is not True or
            auth.get('batch_id') != manifest['batch_id'] or
            auth.get('manifest_sha256') != sha(manifest_path.read_bytes()) or
            auth.get('code_identity') != manifest['code_identity'] or
            auth.get('profile_sha256') != PROFILE_SHA256 or
            auth.get('output_root') != manifest['output_root'] or
            auth.get('planned_order') != manifest['planned_order'] or
            not auth.get('authorization_source')):
        raise PermissionError('single-use Phase-2 authorization identity mismatch')
    return manifest, auth, profile


def classify_output(raw: str, parsed: str | None) -> str:
    context = re.search(r'<context_for_action>(.*?)</context_for_action>',
                        raw, re.DOTALL)
    no_marker = '<no_intervention' in raw
    if context and no_marker:
        return 'mixed_markers'
    if context and context.group(1).strip():
        return 'context_tag_reminder'
    if no_marker and re.fullmatch(r'<no_intervention\s*/>', raw.strip()):
        return 'explicit_no_intervention'
    if no_marker:
        return 'no_intervention_with_explanation'
    if not raw.strip():
        return 'empty_response'
    if context:
        return 'empty_context_tag'
    if parsed is not None:
        raise RuntimeError('parser returned reminder without context tag')
    return 'missing_marker'


async def execute_one(manifest: dict, row: dict, number: int, profile: dict,
                      directory: Path, *, fake_lower=None) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    variant = row['variant']
    prompt, system, projection = request_for(row)
    if projection is not None:
        write_new(directory / 'projection_identity.json', projection)
    agent = construct_upstream(directory / 'upstream', memory_profile=profile,
                               research_candidate=variant)
    install_transport_audit(agent, directory)
    original_call = agent._memory_llm.call
    original_lower = litellm.acompletion
    attempts = 0
    logical_calls = 0
    accepted = False
    capture_fault = None
    started = time.time()
    append_json(directory / 'started.jsonl', {
        'order': number, 'variant': variant, 'arm': row['arm'],
        'pma_step': row['pma_step'], 'started_epoch': started,
        'source_file_sha256': row['source_file_sha256'],
        'request_prompt_sha256': row['request_prompt_sha256'],
        'request_system_sha256': row['request_system_sha256']})

    async def observed_lower(**kwargs):
        nonlocal attempts, accepted, capture_fault
        if capture_fault is not None:
            raise PMAAuditIntegrityError('earlier capture failure forbids sending')
        attempts += 1
        index = attempts
        try:
            append_json(directory / 'provider_attempts_private.jsonl', {
                'attempt': index, 'event': 'request_attempt', 'epoch': time.time(),
                'model': kwargs.get('model'), 'temperature': kwargs.get('temperature'),
                'max_tokens': kwargs.get('max_tokens'), 'thinking': kwargs.get('thinking'),
                'reasoning_effort': kwargs.get('reasoning_effort'),
                'timeout': kwargs.get('timeout'), 'drop_params': kwargs.get('drop_params'),
                'messages': public_value(kwargs.get('messages')),
                'tools': public_value(kwargs.get('tools')),
                'private_endpoint_present': bool(kwargs.get('api_base')),
                'private_key_present': bool(kwargs.get('api_key'))})
        except BaseException as exc:
            capture_fault = exc
            raise
        try:
            response = await (fake_lower(**kwargs) if fake_lower is not None
                              else original_lower(**kwargs))
            accepted = True
            try:
                append_json(directory / 'provider_attempts_private.jsonl', {
                    'attempt': index, 'event': 'response_returned', 'epoch': time.time(),
                    'returned_model': response.get('model'),
                    'choices': public_value(response.get('choices')),
                    'usage': public_value(response.get('usage'))})
            except BaseException as exc:
                capture_fault = exc
                raise
            return response
        except PMAAuditIntegrityError:
            raise
        except BaseException as exc:
            if not accepted:
                try:
                    append_json(directory / 'provider_attempts_private.jsonl', {
                        'attempt': index, 'event': 'request_exception',
                        'error_type': type(exc).__name__,
                        'server_execution': 'unknown', 'epoch': time.time()})
                except BaseException as write_error:
                    capture_fault = write_error
                    raise
            raise

    async def audited_call(*, prompt: str, system: str, tools=None):
        nonlocal logical_calls, capture_fault
        if (logical_calls != 0 or tools is not None or
                prompt != expected_prompt or system != expected_system):
            raise PMAAuditIntegrityError('unexpected Phase-2 call or model-visible input')
        logical_calls += 1
        try:
            append_json(directory / 'requests.jsonl', {
                'logical_call': 1, 'phase': 'context_decision',
                'epoch': time.time(), 'system': system, 'prompt': prompt,
                'tools': tools, 'prompt_sha256': sha(prompt.encode()),
                'system_sha256': sha(system.encode())})
            response = await original_call(prompt=prompt, system=system, tools=tools)
            if capture_fault is not None:
                raise PMAAuditIntegrityError('accepted response capture failed')
            append_json(directory / 'responses.jsonl', {
                'logical_call': 1, 'event': 'response_returned',
                'epoch': time.time(), 'content': response.content,
                'usage': public_value(response.usage),
                'tool_calls': public_value(response.tool_calls)})
            return response
        except BaseException as exc:
            try:
                append_json(directory / 'responses.jsonl', {
                    'logical_call': 1, 'event': 'exception', 'epoch': time.time(),
                    'error_type': type(exc).__name__,
                    'server_execution': 'unknown' if attempts else 'not_sent'})
            except BaseException as write_error:
                capture_fault = write_error
            raise

    expected_prompt, expected_system = prompt, system
    agent._memory_llm.call = audited_call
    litellm.acompletion = observed_lower
    result = {'order': number, 'arm': row['arm'], 'pma_step': row['pma_step'],
              'variant': variant, 'started_epoch': started,
              'model_prompt_sha256': row['request_prompt_sha256'],
              'model_system_sha256': row['request_system_sha256']}
    if projection is not None:
        result.update(input_view=row['input_view'], occurrence=row['occurrence'],
                      run_id=row['run_id'])
    try:
        response = await agent._memory_agent._call_llm_phase2(prompt)
        parsed = agent._memory_agent._parse_phase2_response(response.content or '')
        result.update(status='completed', raw_content=response.content,
                      parsed_reminder=parsed,
                      output_class=classify_output(response.content or '', parsed),
                      returned_usage=public_value(response.usage))
        if logical_calls != 1 or capture_fault is not None:
            raise PMAAuditIntegrityError('Phase-2 call or capture incomplete')
    except BaseException as exc:
        result.update(status=('capture_integrity_failure' if
                              isinstance(exc, PMAAuditIntegrityError) or capture_fault
                              else 'transport_final_failure'),
                      error_type=type(exc).__name__,
                      server_execution='unknown' if attempts else 'not_sent')
    finally:
        litellm.acompletion = original_lower
        result.update(logical_requests=logical_calls, observable_litellm_calls=attempts,
                      deeper_network_attempts='unknown',
                      accepted_response_observed=accepted,
                      ended_epoch=time.time())
        write_new(directory / 'result.json', result)
    return result


async def run_authorized(manifest_path: Path, auth_path: Path, profile_path: Path,
                         *, fake_lower=None) -> list[dict]:
    manifest, auth, profile = check_authorized(manifest_path, auth_path, profile_path)
    root = Path(manifest['output_root'])
    root.mkdir(parents=True, exist_ok=False)
    write_new(root / 'authorization_consumed.json', {
        'batch_id': manifest['batch_id'],
        'manifest_sha256': sha(manifest_path.read_bytes()),
        'authorization_sha256': sha(auth_path.read_bytes()),
        'code_commit': manifest['code_identity']['commit'],
        'profile_sha256': PROFILE_SHA256, 'epoch': time.time()})
    results = []
    try:
        for number, row in enumerate(manifest['planned_order'], 1):
            # Stop before every send if the frozen code, profile, source or order drifts.
            check_frozen_after_start(manifest_path, manifest, profile_path,
                                     auth['manifest_sha256'])
            result = await execute_one(manifest, row, number, profile,
                                       root / slot_name(row, number, manifest['schema']),
                                       fake_lower=fake_lower)
            results.append(result)
            append_json(root / 'summary.jsonl', result)
            print(json.dumps({'order': number, 'status': result['status'],
                              'observable_litellm_calls': result['observable_litellm_calls']}),
                  flush=True)
            if result['status'] != 'completed':
                break
    finally:
        try:
            statuses = []
            for number, row in enumerate(manifest['planned_order'], 1):
                slot = root / slot_name(row, number, manifest['schema'])
                result_file = slot / 'result.json'
                state = (json.loads(result_file.read_text(encoding='utf-8'))['status']
                         if result_file.is_file() else
                         'started_incomplete' if slot.exists() else 'confirmed_not_started')
                statuses.append({'order': number, 'arm': row['arm'],
                                 'pma_step': row['pma_step'], 'variant': row['variant'],
                                 'input_view': row.get('input_view'),
                                 'occurrence': row.get('occurrence'),
                                 'run_id': row.get('run_id'), 'status': state})
            write_new(root / 'status_table.json', {'rows': statuses})
            write_new(root / 'authorization_revoked.json', {
                'batch_id': manifest['batch_id'], 'epoch': time.time(),
                'completed_or_failed_items': len(results),
                'remaining_confirmed_not_started': sum(
                    row['status'] == 'confirmed_not_started' for row in statuses)})
        finally:
            auth_path.unlink(missing_ok=True)
    return results


def check_frozen_after_start(manifest_path: Path, manifest: dict,
                             profile_path: Path, manifest_sha256: str) -> None:
    profile, safe = checked_profile(profile_path)
    if (sha(manifest_path.read_bytes()) != manifest_sha256 or
            json.loads(manifest_path.read_text(encoding='utf-8')) != manifest or
            manifest['code_identity'] != code_identity() or
            manifest['profile_public'] != safe or
            manifest['planned_order'] != planned(manifest['schema']) or
            profile['read_timeout'] != manifest['request_timeout_seconds']):
        raise PermissionError('frozen Phase-2 identity changed during batch')


async def fake(manifest_path: Path, output: Path) -> dict:
    frozen = json.loads(manifest_path.read_text(encoding='utf-8'))
    if (frozen.get('schema') not in
            ('pma-decision-phase2-screen-draft-v1', VIEW_DRAFT_SCHEMA) or
            frozen.get('execution_authorized') is not False or
            frozen.get('planned_order') != planned(frozen['schema'])):
        raise RuntimeError('Phase 2 draft/source/variant identity changed')
    output.mkdir(parents=True, exist_ok=False)
    captures = []
    for number, row in enumerate(frozen['planned_order'], 1):
        variant = row['variant']
        expected_prompt, expected_system, projection = request_for(row)
        slot = output / f'{number:02d}'
        slot.mkdir()
        if projection is not None:
            write_new(slot / 'projection_identity.json', projection)
        agent = construct_upstream(slot / 'upstream',
                                   research_candidate=variant)
        sent = []

        async def fake_call(*, prompt, system, tools=None):
            sent.append({'prompt': prompt, 'system': system, 'tools': tools})
            return LLMResponse(content='<no_intervention/>')

        agent._memory_llm.call = fake_call
        response = await agent._memory_agent._call_llm_phase2(expected_prompt)
        parsed = agent._memory_agent._parse_phase2_response(response.content)
        if (sent != [{'prompt': expected_prompt, 'system': expected_system,
                      'tools': None}] or parsed is not None):
            raise RuntimeError('actual Phase 2 call/parser differs from draft')
        captures.append({'order': number, 'arm': row['arm'],
                         'pma_step': row['pma_step'], 'variant': variant,
                         'input_view': row.get('input_view'),
                         'occurrence': row.get('occurrence'),
                         'request': sent[0], 'raw_response': response.content,
                         'parsed_reminder': parsed})
    (output / 'actual_requests.json').write_text(json.dumps(captures, indent=2,
        ensure_ascii=False), encoding='utf-8')
    return {'fake_requests': len(captures), 'provider_requests': 0,
            'output_sha256': sha((output / 'actual_requests.json').read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prepared = sub.add_parser('prepare')
    prepared.add_argument('--output', type=Path, required=True)
    prepared.add_argument('--input-views', action='store_true')
    replay = sub.add_parser('fake')
    replay.add_argument('--manifest', type=Path, required=True)
    replay.add_argument('--output', type=Path, required=True)
    frozen = sub.add_parser('freeze', help='new unapproved real-input manifest')
    frozen.add_argument('--manifest', type=Path, required=True)
    frozen.add_argument('--output', type=Path, required=True)
    frozen.add_argument('--profile', type=Path, required=True)
    frozen.add_argument('--input-views', action='store_true')
    approved = sub.add_parser('authorize', help='one-use approval after committed code freeze')
    approved.add_argument('--manifest', type=Path, required=True)
    approved.add_argument('--authorization', type=Path, required=True)
    approved.add_argument('--profile', type=Path, required=True)
    approved.add_argument('--authorization-source', required=True)
    launched = sub.add_parser('run', help='real Phase 2 calls; requires one-use approval')
    launched.add_argument('--manifest', type=Path, required=True)
    launched.add_argument('--authorization', type=Path, required=True)
    launched.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.output, input_views=args.input_views)
    elif args.command == 'fake':
        result = asyncio.run(fake(args.manifest, args.output))
    elif args.command == 'freeze':
        result = freeze(args.manifest, args.output, args.profile,
                        input_views=args.input_views)
    elif args.command == 'authorize':
        result = authorize(args.manifest, args.authorization, args.profile,
                           args.authorization_source)
    else:
        rows = asyncio.run(run_authorized(args.manifest, args.authorization,
                                          args.profile))
        planned_count = len(json.loads(args.manifest.read_text(encoding='utf-8'))['planned_order'])
        result = {'completed': sum(row['status'] == 'completed' for row in rows),
                  'started': len(rows), 'confirmed_not_started': planned_count - len(rows)}
    print(json.dumps(result, indent=2))
    if args.command == 'run' and result['completed'] != planned_count:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
