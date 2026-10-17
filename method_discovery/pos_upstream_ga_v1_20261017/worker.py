"""Isolated PoS process. JSON-line IPC; no Task tools or PMA imports."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
from pathlib import Path
import sys
import time


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class RoleTransport:
    def __init__(self, *, mode, replies=None, profile=None, archive):
        self.mode = mode
        self.replies = {key: list(value) for key, value in (replies or {}).items()}
        self.profile = profile
        self.archive = archive
        self.calls = []
        self.sessions = {}
        if mode not in {'fake', 'profile'}:
            raise ValueError('PoS transport must explicitly be fake or profile')
        if mode == 'profile':
            if not isinstance(profile, dict) or not profile.get('apikey') or not profile.get('apibase'):
                raise ValueError('authorized private GA profile is required')

    def caller(self, role):
        def call(messages):
            started = time.monotonic()
            record = {'role': role, 'attempt': len(self.calls) + 1,
                      'messages': messages, 'status': 'attempted'}
            self.calls.append(record)
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
                    response, usage = self._profile_call(role, messages)
                record.update(status='returned', response=response, usage=usage,
                              elapsed_seconds=time.monotonic() - started)
                self.archive.log('pos_role_response', **record)
                return response
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
            cfg['max_tokens'] = 4096 if role == 'belief' else 512
            self.sessions[role] = llmcore.NativeClaudeSession(cfg)
        session = self.sessions[role]
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
            with contextlib.redirect_stdout(sys.stderr):
                generator = session.raw_ask(request)
                try:
                    while True:
                        next(generator)
                except StopIteration as done:
                    blocks = done.value or []
        finally:
            llmcore._record_usage = original
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
    args = parser.parse_args()
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
    transport = RoleTransport(mode=args.mode, replies=replies, profile=profile, archive=logger)
    episode = None
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
                        progress_call=transport.caller('progress'))
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
                elif kind == 'finish':
                    value = episode.finish(reason=command['reason'],
                                           observation=command.get('observation'))
                    logger.log('pos_episode_result', result=value)
                elif kind == 'get_result':
                    value = episode.get_result()
                else:
                    raise ValueError('unknown PoS worker command')
                print(_json({'status': 'ok', 'result': value}), flush=True)
            except BaseException as error:
                logger.log('pos_worker_command_error', kind=kind,
                           error_type=type(error).__name__, error=str(error))
                print(_json({'status': 'error', 'error_type': type(error).__name__,
                             'error': str(error)}), flush=True)
                break
    finally:
        if episode is not None:
            episode.manager.close()
        logger.close()


if __name__ == '__main__':
    main()
