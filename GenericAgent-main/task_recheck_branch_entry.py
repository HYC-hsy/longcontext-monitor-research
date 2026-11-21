"""Isolated four-turn Task continuation from a private pre-request packet.

Run only inside an independent Docker clone. It does not start PMA, call the
manager, run a verifier, or write to the original task container.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import time

from agent_loop import agent_runner_loop
from agentmain import GenericAgent
from ga import GenericAgentHandler
from task_recheck_branch import branch_messages, load_frozen, restore_native_state


def run(packet: Path, arm: str, output: Path, *, agent=None, max_turns: int = 4,
        workspace: Path = Path('/app'), remove_packet: bool = False):
    if max_turns != 4:
        raise ValueError('short branch budget is exactly four Task turns')
    if any(os.environ.get(key) == '1' for key in
           ('GA_PMA_UPSTREAM_ENABLED', 'GA_PMA_ENABLED', 'GA_MONITOR_ENABLED',
            'GA_STATEFUL_MEMORY_ENABLED', 'GA_POS_ENABLED')):
        raise RuntimeError('short branch must have every auxiliary writer disabled')
    row = load_frozen(packet)
    if remove_packet:
        packet.unlink()
    if agent is None:
        agent = GenericAgent()
    workspace = Path(workspace).resolve(strict=True)
    agent.task_dir = str(workspace)
    agent.workspace_dir = str(workspace)
    agent.history = list(row['handler_history_info'])
    handler = GenericAgentHandler(agent, agent.history, str(workspace))
    restore_native_state(row, agent.llmclient, handler)
    agent.handler = handler
    agent.llmclient.log_path = str(output.parent / 'model_responses.txt')
    output.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    visible = []
    events = []
    original_chat = agent.llmclient.chat
    def recording_chat(*args, **kwargs):
        messages = kwargs.get('messages', args[0] if args else None)
        tools = kwargs.get('tools', args[1] if len(args) > 1 else None)
        events.append({'kind': 'task_request_prepared',
                       'messages': copy.deepcopy(messages),
                       'tools': copy.deepcopy(tools)})
        return (yield from original_chat(*args, **kwargs))
    agent.llmclient.chat = recording_chat
    original_turn_end = handler.turn_end_callback
    def recording_turn_end(response, tool_calls, tool_results, turn,
                           next_prompt, exit_reason):
        result = original_turn_end(response, tool_calls, tool_results, turn,
                                   next_prompt, exit_reason)
        events.append({'kind': 'task_turn_result', 'turn': turn,
                       'public_response': getattr(response, 'content', '') or '',
                       'tool_calls': copy.deepcopy(tool_calls),
                       'tool_results': copy.deepcopy(tool_results),
                       'next_prompt': result, 'exit_reason': copy.deepcopy(exit_reason)})
        return result
    handler.turn_end_callback = recording_turn_end
    gen = agent_runner_loop(agent.llmclient, row['backend_system'],
                            row['initial_task'], handler, row['tools_schema'],
                            max_turns=max_turns, verbose=False, yield_info=True,
                            turn_offset=row['actor_attempt'] - 1,
                            continuation_messages=branch_messages(row, arm))
    error = None
    try:
        while True:
            visible.append(next(gen))
    except StopIteration as done:
        terminal = done.value
    except BaseException as exc:
        terminal = {'result': 'EXCEPTION'}
        error = {'type': type(exc).__name__, 'message': str(exc)}
    result = {
        'schema': 'task-recheck-branch-result-v1',
        'parent_run_id': row['run_id'], 'actor_attempt_at_cut': row['actor_attempt'],
        'arm': arm, 'max_task_turns': max_turns, 'terminal': terminal,
        'started_at_epoch': started, 'ended_at_epoch': time.time(),
        'visible_stream': visible, 'visible_events': events,
        'error': error,
    }
    with output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, default=str)
    if error is not None:
        raise RuntimeError('short Task branch failed; private partial result preserved')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--arm', choices=('none', 'fixed', 'targeted'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--remove-packet', action='store_true')
    args = parser.parse_args()
    run(args.packet, args.arm, args.output, remove_packet=args.remove_packet)


if __name__ == '__main__':
    main()
