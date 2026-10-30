"""Host-side candidate PMA transport over the existing single-run event spool.

The PMA bank and process remain in the isolated PoS worker. This process owns
only the original pinned PMA LiteLLM transport and its private profile.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import time

from episode import construct_upstream
from event_spool import EventDispatcher
from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2
from harbor.agents.terminus_2.terminus_2 import Terminus2


def _durable(path: Path, row: dict) -> None:
    with path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


class TransportEpisode:
    def __init__(self, llm, *, run_id, task_id, archive, research_candidate):
        self.llm, self.run_id, self.task_id = llm, run_id, task_id
        self.archive = archive
        self.ended = False
        self.sequence = 0
        self.research_candidate = research_candidate

    async def handle(self, event):
        if event.get('kind') != 'candidate_pma_call' or event.get('sequence') != self.sequence + 1:
            raise ValueError('candidate PMA call sequence or kind invalid')
        role = event.get('role')
        tools = event.get('tools')
        if role not in {'pma_phase1', 'pma_phase2'} or (tools is not None) != (role == 'pma_phase1'):
            raise ValueError('candidate PMA role/tools mismatch')
        prompt, system = event.get('prompt'), event.get('system')
        if not isinstance(prompt, str) or not isinstance(system, str):
            raise ValueError('candidate PMA prompt/system missing')
        request_bytes = len(json.dumps({'prompt': prompt, 'system': system,
            'tools': tools}, ensure_ascii=False).encode('utf-8'))
        if self.research_candidate != 'pos_pma_shared_view_v1' and request_bytes > 90000:
            raise ValueError('candidate complete PMA role input exceeds byte budget')
        self.sequence += 1
        request_id = event['event_id']
        _durable(self.archive / 'requests.jsonl', {'event_id': request_id,
            'role': role, 'prompt': prompt, 'system': system, 'tools': tools})
        try:
            response = await self.llm.call(prompt=prompt, system=system, tools=tools)
            calls = []
            for call in getattr(response, 'tool_calls', None) or []:
                function = call.function
                arguments = function.arguments
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                calls.append({'name': function.name, 'arguments': arguments})
            result = {'content': getattr(response, 'content', None) or '',
                      'tool_calls': calls}
            _durable(self.archive / 'responses.jsonl', {'event_id': request_id,
                'role': role, 'result': result, 'status': 'returned'})
            return result
        except BaseException as error:
            _durable(self.archive / 'responses.jsonl', {'event_id': request_id,
                'role': role, 'status': 'failed', 'error_type': type(error).__name__})
            raise


async def serve(args):
    root = Path(__file__).resolve().parent
    vendor = root / 'vendor' / 'pma_89e5c0d'
    if not (Path(inspect.getfile(MemoryEnabledTerminus2)).resolve().is_relative_to(vendor / 'src')
            and Path(inspect.getfile(Terminus2)).resolve().is_relative_to(vendor / 'external' / 'harbor' / 'src')):
        raise RuntimeError('candidate transport did not load pinned PMA sources')
    private = Path(args.private_root).resolve()
    requests = Path(args.requests).resolve(strict=True)
    responses = Path(args.responses).resolve(strict=True)
    if private.exists() or private.is_relative_to(requests.parent) or requests == responses:
        raise RuntimeError('candidate transport private/spool boundary invalid')
    private.mkdir(parents=True)
    archive = private / 'archive'
    archive.mkdir()
    profile_path = Path(os.environ['PMA_MEMORY_PROFILE_FILE']).resolve(strict=True)
    raw = profile_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != os.environ.get('PMA_MEMORY_PROFILE_SHA256'):
        raise RuntimeError('candidate PMA profile bytes differ')
    profile = json.loads(raw)['claude_monitor_opus48']
    agent = construct_upstream(private / 'upstream_agent', memory_profile=profile)
    episode = TransportEpisode(agent._memory_llm, run_id=args.run_id,
                               task_id=args.task_id, archive=archive,
                               research_candidate=args.research_candidate)
    dispatcher = EventDispatcher(episode, requests, responses,
                                 deadline_epoch=args.deadline_epoch)
    (private / 'worker_ready.json').write_text(json.dumps({
        'run_id': args.run_id, 'task_id': args.task_id, 'fake_memory': False,
        'research_candidate': args.research_candidate,
        'pma_budget': {'input_limit_utf8_bytes': (None if
            args.research_candidate == 'pos_pma_shared_view_v1' else 90000),
            'ga_history_context_win': profile.get('context_win', 30000),
            'provider_context_limit_tokens': profile.get('model_context_limit_tokens'),
            'output_reserve_max_tokens': profile.get('max_tokens'),
            'basis': 'serialized_utf8_bytes_not_provider_token_limit'}},
        sort_keys=True), encoding='utf-8')
    reason = 'host_stop'
    active = None
    try:
        while not (private / 'stop.request').exists():
            if args.deadline_epoch is not None and time.time() >= args.deadline_epoch:
                reason = 'deadline'
                break
            active = asyncio.create_task(dispatcher.serve_once())
            while not active.done():
                await asyncio.wait({active}, timeout=.05)
                if ((private / 'stop.request').exists() or
                        (args.deadline_epoch is not None and time.time() >= args.deadline_epoch)):
                    reason = 'stopped_or_deadline_in_flight_unknown'
                    active.cancel()
                    break
            if reason == 'stopped_or_deadline_in_flight_unknown':
                break
            await active
            await asyncio.sleep(.05)
    finally:
        (private / 'worker_exit.json').write_text(json.dumps({
            'run_id': args.run_id, 'task_id': args.task_id,
            'reason': reason, 'last_sequence': episode.sequence}, sort_keys=True),
            encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--private-root', required=True)
    parser.add_argument('--requests', required=True)
    parser.add_argument('--responses', required=True)
    parser.add_argument('--deadline-epoch', type=lambda value: None if value == 'uncapped' else float(value), required=True)
    parser.add_argument('--research-candidate', choices=(
        'pos_pma_complement_v1', 'pos_pma_shared_view_v1'),
        default='pos_pma_complement_v1')
    asyncio.run(serve(parser.parse_args()))
