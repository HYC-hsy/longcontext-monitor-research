"""Isolated PoS process. JSON-line IPC; no Task tools or PMA imports."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


ROLE_JSON_CONTRACT_VERSION = 'pos-role-json-object-fence-v1'
ROLE_INPUT_CONTRACT_VERSION = 'pos-ga-input-contract-v1'
ROLE_OBJECT_INSTRUCTION = (
    'PoS JSON output contract: the entire public response must be exactly one '
    'complete JSON object. Do not use a Markdown code fence, explanatory text '
    'before or after it, or a second object.'
)
ROLE_UPDATE_FIELDS_INSTRUCTION = (
    'PoS incremental World record interface (the original requested update '
    'schema and validator remain authoritative): each upsert_entities item is '
    'an Entity with required entity_id, entity_type, name; attributes defaults '
    'to {}. Each upsert_states item is a State with required state_id, '
    'entity_id, description; probability defaults to 1.0, reason to null, '
    'source_type to "observed". Each upsert_relations item is a Relation with '
    'required relation_id, source_id, target_id, description; probability '
    'defaults to 0.5, reason to null, source_type to "observed". For Relation '
    'only, the original normalizer accepts source_entity_id/src_entity_id/'
    'source/src as aliases for source_id, target_entity_id/dst_entity_id/'
    'target/dst as aliases for target_id, and relation_type/relation/type '
    'as aliases for description. These are accepted aliases, not extra '
    'required fields.'
)
ROLE_THINKING_TYPE = 'disabled'
ROLE_TEMPERATURE = 0
ROLE_MAX_TOKENS = {'belief': 4096, 'consistency': 512, 'progress': 512}
_JSON_FENCE = re.compile(
    r'(?P<leading>[ \t\r\n]*)(?P<opening>```(?:json)?\r?\n)'
    r'(?P<body>.*?)(?P<closing>\r?\n```)(?P<trailing>[ \t\r\n]*)',
    re.DOTALL,
)


def _strict_object(raw):
    """Check only the newly accepted fenced path; upstream owns all schemas."""
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def reject_constant(_value):
        raise ValueError('nonstandard JSON constant')
    def finite_float(value):
        number = float(value)
        if not (float('-inf') < number < float('inf')):
            raise ValueError('nonfinite JSON number')
        return number
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=reject_constant, parse_float=finite_float)
    if not isinstance(value, dict):
        raise ValueError('JSON value is not an object')


def _adapt_role_json(raw):
    """Remove one enumerated outer fence only around one strict JSON object."""
    match = _JSON_FENCE.fullmatch(raw)
    if match is None:
        return raw, 'unchanged', None
    body = match.group('body')
    try:
        _strict_object(body)
    except (ValueError, TypeError, RecursionError):
        return raw, 'fence_rejected', None
    boundary = {name: match.group(name) for name in
                ('leading', 'opening', 'closing', 'trailing')}
    return body, 'outer_fence_removed', boundary


def _json(value):
    # GA's shipped tool-schema asset contains an escaped lone surrogate.
    # JSON ASCII escaping preserves its exact code point across the pipe.
    return json.dumps(value, ensure_ascii=True, separators=(',', ':'))


def _role_input_contract(role, messages):
    """Append an auditable adapter message without editing upstream messages.

    Fixed upstream update and Sentinel repair prompts retain the first user
    message's Required JSON schema through their bounded correction calls.
    Textualize, initialize, consistency, and progress do not have that schema.
    """
    update = role == 'belief' and any(
        item.get('role') == 'user' and
        'Required JSON schema:' in item.get('content', '') and
        '"upsert_entities"' in item['content'].split('Required JSON schema:', 1)[1]
        for item in messages[:2]
    )
    supplement = ROLE_OBJECT_INSTRUCTION
    if update:
        supplement += '\n\n' + ROLE_UPDATE_FIELDS_INSTRUCTION
    effective = [dict(item) for item in messages]
    effective.append({'role': 'system', 'content': supplement})
    return effective, supplement, 'update_records' if update else 'object_only'


def _persist_receipt(path, *, case_id, status, result=None, error=None,
                     run_id=None, task_id=None):
    """Durable episode receipt; never infer a missing core state as saved."""
    target = path.with_suffix('.result.json')
    payload = {'case_id': case_id, 'run_id': run_id, 'task_id': task_id,
               'status': status, 'result': result,
               'error': error, 'success_known': False}
    data = (_json(payload) + '\n').encode('utf-8')
    with target.open('wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return {'path': str(target), 'bytes': len(data)}


class _DurableProviderSink:
    """The required pre-send record must survive a completed write before HTTP."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, event):
        data = (_json(event) + '\n').encode('utf-8')
        with self.path.open('ab') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())


class RoleTransport:
    def __init__(self, *, mode, replies=None, profile=None, archive,
                 capture_path=None, run_id=None, task_id=None):
        self.mode = mode
        self.replies = {key: list(value) for key, value in (replies or {}).items()}
        self.profile = profile
        self.archive = archive
        self.calls = []
        self.sessions = {}
        self.capture_path = Path(capture_path) if capture_path is not None else None
        self.run_id = run_id
        self.task_id = task_id
        if mode not in {'fake', 'profile'}:
            raise ValueError('PoS transport must explicitly be fake or profile')
        if mode == 'profile':
            if not isinstance(profile, dict) or not profile.get('apikey') or not profile.get('apibase'):
                raise ValueError('authorized private GA profile is required')

    def caller(self, role):
        def call(messages):
            started = time.monotonic()
            effective, supplement, scope = _role_input_contract(role, messages)
            record = {'role': role, 'attempt': len(self.calls) + 1,
                      'messages': effective, 'status': 'attempted'}
            self.calls.append(record)
            self.archive.log('pos_role_input_contract',
                             contract_version=ROLE_INPUT_CONTRACT_VERSION,
                             role=role, attempt=record['attempt'], scope=scope,
                             original_messages=messages, supplement=supplement,
                             supplement_sha256=hashlib.sha256(
                                 supplement.encode('utf-8')).hexdigest(),
                             effective_messages_sha256=hashlib.sha256(
                                 _json(effective).encode('utf-8')).hexdigest())
            self.archive.log('pos_role_request', **record)
            try:
                if self.mode == 'fake':
                    if not self.replies.get(role):
                        raise RuntimeError('fake PoS reply exhausted: ' + role)
                    response = self.replies[role].pop(0)
                    if isinstance(response, dict) and 'raise' in response:
                        raise RuntimeError(str(response['raise']))
                    if not isinstance(response, str):
                        raise TypeError('fake reply must be string')
                    usage = {'status': 'synthetic_not_provider_usage'}
                else:
                    response, usage = self._profile_call(role, effective)
                record.update(status='returned', response=response, usage=usage,
                              elapsed_seconds=time.monotonic() - started)
                self.archive.log('pos_role_response', **record)
                parser_input, transform, boundary = _adapt_role_json(response)
                self.archive.log('pos_role_json_adapter',
                                 contract_version=ROLE_JSON_CONTRACT_VERSION,
                                 role=role, attempt=record['attempt'],
                                 call_identity=f"{role}:{record['attempt']}",
                                 transform=transform, raw_response=response,
                                 raw_sha256=hashlib.sha256(response.encode('utf-8')).hexdigest(),
                                 parser_input=parser_input,
                                 parser_input_sha256=hashlib.sha256(
                                     parser_input.encode('utf-8')).hexdigest(),
                                 removed_boundary=boundary)
                return parser_input
            except BaseException as error:
                record.update(status='failed', error_type=type(error).__name__,
                              error=str(error), elapsed_seconds=time.monotonic() - started)
                self.archive.log('pos_role_error', **record)
                raise
        return call

    def _profile_call(self, role, messages):
        """Reuse GA native transport and private profile; zero hidden transport retries."""
        import llmcore
        if role not in self.sessions:
            cfg = dict(self.profile)
            cfg['max_retries'] = 0
            cfg['max_tokens'] = ROLE_MAX_TOKENS[role]
            cfg['thinking_type'] = ROLE_THINKING_TYPE
            cfg['temperature'] = ROLE_TEMPERATURE
            self.sessions[role] = llmcore.NativeClaudeSession(cfg)
            self.sessions[role].max_retries = 0  # ignore Task retry env override
        session = self.sessions[role]
        overall = float(os.environ.get('GA_POS_DEADLINE_EPOCH', '0') or 0)
        remaining = overall - time.time() if overall else float(
            os.environ.get('GA_POS_TIMEOUT', '180'))
        if remaining <= 0:
            raise TimeoutError('PoS role deadline elapsed before send')
        session.total_response_timeout = min(float(os.environ.get('GA_POS_TIMEOUT', '180')),
                                             remaining)
        self.archive.log('pos_role_transport_resolved', role=role,
                         model=session.model, max_tokens=session.max_tokens,
                         thinking_type=session.thinking_type,
                         temperature=session.temperature, max_retries=session.max_retries,
                         connect_timeout=session.connect_timeout,
                         read_timeout=session.read_timeout,
                         total_response_timeout=session.total_response_timeout,
                         api_mode=session.api_mode)
        system = '\n'.join(item['content'] for item in messages if item['role'] == 'system')
        request = [
            {'role': item['role'], 'content': [{'type': 'text', 'text': item['content']}]}
            for item in messages if item['role'] != 'system'
        ]
        session.system = system
        usages = []
        original = llmcore._record_usage
        def capture(value, api_mode):
            usages.append(dict(value))
            return original(value, api_mode)
        llmcore._record_usage = capture
        try:
            capture_context = contextlib.nullcontext()
            if os.environ.get('GA_PMA_CAPTURE_TASK_REQUESTS') == '1':
                if self.capture_path is None or not self.run_id or not self.task_id:
                    raise RuntimeError('PoS provider capture binding unavailable before send')
                from research_runtime import research_context
                capture_context = research_context(
                    {'experiment_id': 'pos-ga', 'condition_id': 'P',
                     'task_id': self.task_id, 'run_id': self.run_id,
                     'branch_id': 'pos-role-' + role},
                    _DurableProviderSink(self.capture_path))
            with capture_context, contextlib.redirect_stdout(sys.stderr):
                generator = session.raw_ask(request)
                try:
                    while True:
                        next(generator)
                except StopIteration as done:
                    blocks = done.value or []
        finally:
            llmcore._record_usage = original
        if getattr(session, '_research_capture_failed', False):
            raise RuntimeError('PoS provider capture incomplete after accepted response')
        response = '\n'.join(block['text'] for block in blocks if block.get('type') == 'text')
        if not response:
            raise RuntimeError('PoS role returned no text; never fabricate JSON')
        return response, {'provider_usage': usages, 'status': 'captured' if usages else 'unavailable'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vendor', type=Path, required=True)
    parser.add_argument('--episode-module', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--mode', choices=('fake', 'profile'), required=True)
    parser.add_argument('--fake-replies', type=Path)
    parser.add_argument('--profile-file', type=Path)
    parser.add_argument('--profile-name')
    parser.add_argument('--run-id')
    parser.add_argument('--task-id')
    parser.add_argument('--binding-file', type=Path)
    args = parser.parse_args()
    if args.mode == 'profile':
        if not args.binding_file or not args.run_id or not args.task_id:
            raise RuntimeError('PoS profile requires a frozen run/task binding')
        binding = json.loads(args.binding_file.resolve(strict=True).read_text(
            encoding='utf-8'))
        if (binding.get('schema') != 'pos-ga-transport-binding-v1' or
                binding.get('transport') != 'profile' or
                binding.get('run_id') != args.run_id or
                binding.get('task_id') != args.task_id or
                args.binding_file.resolve().parent != args.archive.resolve().parent or
                binding.get('upstream_commit') !=
                    '6818cfa6434dbc91fcf67f0b3eb12a91db47433f' or
                not all(isinstance(binding.get(key), str) and
                        len(binding[key]) == 64 for key in
                        ('manifest_sha256', 'authorization_sha256', 'config_sha256'))):
            raise RuntimeError('PoS profile binding identity invalid')
        def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in (('worker_sha256', Path(__file__)),
                          ('episode_sha256', args.episode_module),
                          ('citation_fix_sha256', args.episode_module.with_name('citation_fix.py')),
                          ('profile_sha256', args.profile_file)):
            if binding.get(key) != digest(path.resolve(strict=True)):
                raise RuntimeError('PoS profile binding bytes differ: ' + key)
        for relative, expected in binding.get('vendor_files_sha256', {}).items():
            part = Path(relative)
            if part.is_absolute() or '..' in part.parts or not part.parts or (
                    digest((args.vendor / part).resolve(strict=True)) != expected):
                raise RuntimeError('PoS vendor binding differs')
    sys.path.insert(0, str(args.vendor.resolve(strict=True)))
    # The GA source bundle contains llmcore.py as a sibling of pos_runtime.
    # This has no effect in fake mode and does not load the private profile.
    sys.path.insert(0, str(args.episode_module.resolve(strict=True).parent.parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location('pos_ga_episode', args.episode_module)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from utils.logger import Logger
    logger = Logger(args.archive)
    replies = json.loads(args.fake_replies.read_text(encoding='utf-8')) if args.mode == 'fake' else None
    profile = None
    if args.mode == 'profile':
        if not args.profile_file or not args.profile_name:
            raise ValueError('profile file/name missing')
        profile_path = args.profile_file.resolve(strict=True)
        if profile_path.suffix == '.json':
            profile = json.loads(profile_path.read_text(encoding='utf-8'))[args.profile_name]
        else:
            # Host-only offline checks may supply an existing private Python
            # profile; the GA bundle uses its gateway-rewritten mykey.json.
            import runpy
            profile = runpy.run_path(str(profile_path))[args.profile_name]
    transport = RoleTransport(mode=args.mode, replies=replies, profile=profile,
                              archive=logger,
                              capture_path=args.archive.with_suffix('.provider.jsonl'),
                              run_id=args.run_id, task_id=args.task_id)
    episode = None
    finished = False
    failure = None
    try:
        for line in sys.stdin:
            command = json.loads(line)
            kind = command['kind']
            try:
                if kind == 'reset':
                    if episode is not None:
                        raise RuntimeError('PoS episode already constructed')
                    episode = module.PoSEpisode(case_id=command['case_id'],
                        config=module.execution_config(), logger=logger,
                        belief_call=transport.caller('belief'),
                        consistency_call=transport.caller('consistency'),
                        progress_call=transport.caller('progress'),
                        citation_fixed=command.get('citation_fixed', False))
                    value = episode.reset(task=command['task'],
                        observation=command['observation'], actions=command['actions'])
                elif episode is None:
                    raise RuntimeError('PoS episode has not reset')
                elif kind == 'decision_view':
                    value = episode.decision_view(current_observation=command['observation'],
                        actions=command['actions'],
                        runtime_constraints=command.get('runtime_constraints', ''))
                elif kind == 'update':
                    value = episode.update(thought=command.get('thought', ''),
                        action_batch=command['action_batch'], observation=command['observation'],
                        done=command.get('done', False))
                elif kind == 'decision_completed':
                    value = episode.decision_completed(turn=command['turn'],
                                                       action_count=command['action_count'])
                elif kind == 'finish':
                    value = episode.finish(reason=command['reason'],
                                           observation=command.get('observation'))
                    logger.log('pos_episode_result', result=value)
                    receipt = _persist_receipt(args.archive, case_id=episode.case_id,
                                               status=value['status'], result=value,
                                               run_id=args.run_id, task_id=args.task_id)
                    logger.log('pos_result_persisted', **receipt)
                    finished = True
                elif kind == 'abort':
                    episode.manager.close()
                    value = episode.get_result()
                    receipt = _persist_receipt(args.archive, case_id=episode.case_id,
                                               status='partial', result=value,
                                               error=command.get('reason'),
                                               run_id=args.run_id, task_id=args.task_id)
                    logger.log('pos_result_persisted', **receipt)
                    finished = True
                elif kind == 'get_result':
                    value = episode.get_result()
                else:
                    raise ValueError('unknown PoS worker command')
                print(_json({'status': 'ok', 'result': value}), flush=True)
            except BaseException as error:
                failure = {'type': type(error).__name__, 'message': str(error),
                           'command': kind}
                logger.log('pos_worker_command_error', kind=kind,
                           error_type=type(error).__name__, error=str(error))
                print(_json({'status': 'error', 'error_type': type(error).__name__,
                             'error': str(error)}), flush=True)
                break
    finally:
        if episode is not None:
            try:
                episode.manager.close()
                if not finished:
                    try:
                        # reset() may have committed a core state before a
                        # later initialization/textualization stage failed.
                        partial = episode.get_result()
                    except BaseException as error:
                        partial = None
                        failure = {**(failure or {}), 'snapshot_error':
                                   type(error).__name__ + ': ' + str(error)}
                    receipt = _persist_receipt(args.archive, case_id=episode.case_id,
                                               status='partial' if partial else 'missing',
                                               result=partial, error=failure or 'EOF',
                                               run_id=args.run_id, task_id=args.task_id)
                    logger.log('pos_partial_persisted', **receipt)
            except BaseException as error:
                logger.log('pos_partial_missing', error_type=type(error).__name__,
                           error=str(error))
        logger.close()


if __name__ == '__main__':
    main()
