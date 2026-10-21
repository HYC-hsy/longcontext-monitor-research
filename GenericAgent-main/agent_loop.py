import inspect, json, re, os, sys
from dataclasses import dataclass
from typing import Any, Optional
from research_runtime import CompletionProposal, decide_completion, emit as _research_emit, telemetry_enabled as _telemetry_enabled, consume_provider_call as _consume_provider_call, register_pending_pma_reminder as _register_pending_pma_reminder, sha256_json as _sha256_json
from experiment_conditions import condition_initial_task
from llmcore import ProviderResponseCancelled
try: from plugins.hooks import trigger as _hook
except ImportError: _hook = lambda *a, **k: None
@dataclass
class StepOutcome:
    data: Any
    next_prompt: Optional[str] = None
    should_exit: bool = False
def try_call_generator(func, *args, **kwargs):
    ret = func(*args, **kwargs)
    if hasattr(ret, '__iter__') and not isinstance(ret, (str, bytes, dict, list)): ret = yield from ret
    return ret

class BaseHandler:
    def turn_end_callback(self, response, tool_calls, tool_results, turn, next_prompt, exit_reason): return next_prompt
    def observe_tool_outcome(self, data, turn): return None
    def dispatch(self, tool_name, args, response, index=0, tool_num=1):
        method_name = f"do_{tool_name}"
        if hasattr(self, method_name):
            args['_index'] = index; args['_tool_num'] = tool_num
            _hook('tool_before', locals())
            ret = yield from try_call_generator(getattr(self, method_name), args, response)
            _hook('tool_after', locals())
            return ret
        elif tool_name == 'bad_json': return StepOutcome(None, next_prompt=args.get('msg', 'bad_json'), should_exit=False)
        else:
            yield f"未知工具: {tool_name}\n"
            return StepOutcome(None, next_prompt=f"未知工具 {tool_name}", should_exit=False)

def json_default(o): return list(o) if isinstance(o, set) else str(o)

def _pos_public_value(value):
    """JSON-only host projection; never stringify a response object's repr."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_pos_public_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _pos_public_value(item) for key, item in value.items()}
    return {'availability': 'non_json_host_value', 'type': type(value).__name__}

def _pos_terminal_observation(turn, response, receipts, reason):
    return json.dumps({'source': 'GA_terminal_observation', 'turn': turn,
        'public_response_content': getattr(response, 'content', '') or '',
        'tool_results': [_pos_public_value(item) for item in receipts],
        'host_terminal': {'result': reason.get('result', 'CURRENT_TASK_DONE'),
                          'public_data': _pos_public_value(reason.get('data'))}},
        ensure_ascii=False)
def exhaust(g):
    try: 
        while True: next(g)
    except StopIteration as e: return e.value

def get_pretty_json(data):
    if isinstance(data, dict) and "script" in data:
        data = data.copy(); data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace('\\n', '\n')

def _agent_runner_loop_impl(client, system_prompt, user_input, handler, tools_schema,
                      max_turns=40, verbose=True, initial_user_content=None, yield_info=False,
                      turn_offset=0):
    initial_content = initial_user_content if initial_user_content is not None else user_input
    initial_content = condition_initial_task(
        initial_content, getattr(handler.parent, 'research_condition', None)
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": initial_content}
    ]
    local_turn = 0; turn = int(turn_offset); handler.max_turns = max_turns
    exit_reason = {}; response = None
    _hook('agent_before', locals())
    pma = None
    pma_upstream = None
    pos = None
    stateful = None
    stateful_setting = os.environ.get('GA_STATEFUL_MEMORY_ENABLED', '0')
    if stateful_setting not in {'0', '1'}:
        raise ValueError('invalid stateful-memory enable value')
    stateful_enabled = stateful_setting == '1'
    if stateful_enabled:
        if any(os.environ.get(name) == '1' for name in (
                'GA_POS_ENABLED', 'GA_PMA_UPSTREAM_ENABLED', 'GA_PMA_ENABLED',
                'GA_MONITOR_ENABLED', 'GA_M0_MONITOR_ENABLED',
                'GA_POS_PMA_COMPLEMENT', 'GA_POS_PMA_SHARED_VIEW')):
            raise ValueError('stateful memory is exclusive of prior auxiliary modes')
        stateful_mode = os.environ.get('GA_STATEFUL_MEMORY_MODE')
        if stateful_mode not in {'fake-only', 'live'}:
            raise ValueError('stateful memory requires fake-only or bound live mode')
        if (os.environ.get('GA_TASK_COMPLETE_RESPONSE') != '1' or
                not getattr(getattr(client, 'backend', None),
                            'task_complete_response', False)):
            raise ValueError('stateful memory requires bound complete-response Task')
        from urllib.parse import urlsplit
        backend = client.backend
        if getattr(backend, 'max_retries', None) != 0:
            raise ValueError('stateful Task requires effective max_retries=0')
        if stateful_mode == 'fake-only':
            endpoint = urlsplit(getattr(backend, 'api_base', ''))
            if (endpoint.scheme != 'http' or endpoint.hostname not in
                    {'127.0.0.1', 'localhost', '::1'} or
                    getattr(backend, 'api_key', None) != 'synthetic-only'):
                raise ValueError('stateful fake Task requires loopback and synthetic key')
            from stateful_memory_bridge import StatefulMemoryBridge
            stateful = StatefulMemoryBridge.from_environment(initial_content,
                                                             turn_offset=turn_offset)
        else:
            from stateful_memory_bridge import StatefulLiveBridge
            stateful = StatefulLiveBridge.from_environment(initial_content,
                                                           turn_offset=turn_offset)
            backend.stateful_native_preflight = stateful.native_preflight
        handler.parent._stateful_memory_bridge = stateful
    shared_view = os.environ.get('GA_POS_PMA_SHARED_VIEW') == '1'
    if shared_view and os.environ.get('GA_POS_PMA_COMPLEMENT') == '1':
        raise ValueError('shared-view and previous complement are exclusive')
    complement = (os.environ.get('GA_POS_PMA_COMPLEMENT') == '1' or shared_view)
    if complement and os.environ.get('GA_POS_ENABLED') != '1':
        raise ValueError('complement requires an explicit PoS worker')
    pos_observation = initial_content
    pos_auxiliary_errors = []
    pos_integrity_failed = False
    def pos_record(kind, payload):
        nonlocal pos_integrity_failed
        if pos is None:
            return
        if complement and pos_integrity_failed:
            return
        try:
            pos.record_host(kind, payload)
        except (OSError, TypeError, ValueError) as error:
            # The host action/terminal is already known in memory. Archive
            # failure is auxiliary, never a change to the Task result.
            pos_auxiliary_errors.append({'kind': kind, 'error_type':
                                         type(error).__name__})
            if complement:
                pos_integrity_failed = True
                # Do not send another Task or auxiliary inference after a
                # required candidate host receipt is lost. Closing stdin lets
                # the worker persist whatever partial state it already owns.
                try:
                    pos.close()
                except BaseException as cleanup_error:
                    pos_auxiliary_errors.append({'kind': 'candidate_close_after_capture_failure',
                                                 'error_type': type(cleanup_error).__name__})
                if not exit_reason:
                    raise RuntimeError('candidate required host capture failed') from error
    if os.environ.get('GA_POS_ENABLED') == '1':
        if any(os.environ.get(name) == '1' for name in (
                'GA_PMA_UPSTREAM_ENABLED', 'GA_PMA_ENABLED',
                'GA_MONITOR_ENABLED', 'GA_M0_MONITOR_ENABLED')):
            raise ValueError('PoS is exclusive of PMA and monitor modes')
        if int(turn_offset) != 0:
            raise ValueError('PoS requires a fresh Task episode')
        from pos_bridge import PoSBridge
        pos = PoSBridge.from_environment()
        handler.parent._pos_bridge = pos
        handler.parent.pos_decision_context = not complement
        pos.exchange('reset', case_id=os.environ.get('GA_BENCH_TASK_ID', 'offline-task'),
                     task=initial_content, observation=initial_content,
                     actions=tools_schema,
                     citation_fixed=os.environ.get('GA_POS_CITATION_FIXED') == '1',
                     candidate=complement,
                     candidate_method=('pos_pma_shared_view_v1' if shared_view else
                         'pos_pma_complement_v1' if complement else None))
    if os.environ.get('GA_PMA_UPSTREAM_ENABLED') == '1':
        if (os.environ.get('GA_PMA_ENABLED') == '1' or
                os.environ.get('GA_MONITOR_ENABLED') == '1' or
                os.environ.get('GA_M0_MONITOR_ENABLED') == '1'):
            raise ValueError('Complete upstream PMA cannot be combined with old PMA or Monitor')
        from pma_upstream_bridge import UpstreamPMAClient
        pma_upstream = UpstreamPMAClient.from_environment(
            initial_content, turn_offset=turn_offset)
        handler.parent.pma_upstream_bridge = pma_upstream
    if os.environ.get('GA_PMA_ENABLED') == '1':
        from pma_baseline.runtime import from_environment
        pma = from_environment(initial_content)
    while (stateful_enabled and stateful_mode == 'live' and
           os.environ.get('GA_STATEFUL_UNCAPPED_TOTAL') == '1') or \
            local_turn < handler.max_turns:
        wait_correction = getattr(handler.parent, 'wait_monitor_correction', None)
        if wait_correction is not None and not wait_correction():
            break
        local_turn += 1; turn = int(turn_offset) + local_turn
        monitor_runtime = getattr(handler.parent, 'monitor_runtime', None)
        note_task_turn = getattr(monitor_runtime, 'note_task_turn', None)
        if note_task_turn is not None:
            note_task_turn(local_turn)
        consume_resume = getattr(handler.parent, 'consume_resumable_interruption', None)
        current_correction = ''
        if consume_resume is not None:
            resumed = consume_resume()
            if resumed:
                injection = "\n\n".join(
                    f"[MONITOR CORRECTION]\n{item['message']}" for item in resumed
                )
                current_correction = injection
                if messages and messages[-1].get("role") == "user":
                    content = messages[-1].get("content", "")
                    if isinstance(content, str):
                        messages[-1]["content"] = content + "\n\n" + injection
                    else:
                        messages.append({"role": "user", "content": injection})
                else:
                    messages.append({"role": "user", "content": injection})
                handler.code_stop_signal.clear()
        turnstr = f'LLM Running (Turn {turn}) ...'
        if handler.parent.task_dir: turnstr = f'Turn {turn} ...'
        if verbose: turnstr = f'**{turnstr}**'
        if yield_info: yield {'turn': turn}
        yield f"\n\n{turnstr}\n\n"
        if turn%10 == 0: client.last_tools = ''  # 每10轮重置一次工具描述
        _hook('turn_before', locals())
        if pma is not None:
            pma.review()
            reminder = pma.take_reminder()
            if reminder:
                # Upstream user_turn appends to the current input, not a new turn.
                from pma_baseline.runtime import append_reminder
                messages[-1] = append_reminder(messages[-1], reminder)
        if pma_upstream is not None:
            reminder = pma_upstream.before_actor_call(turn)
            if reminder:
                from pma_upstream_bridge import append_reminder
                messages[-1] = append_reminder(messages[-1], reminder)
                if (_telemetry_enabled() and
                        os.environ.get('GA_PMA_CAPTURE_TASK_REQUESTS') == '1'):
                    event = _research_emit('pma_reminder_appended', {
                        'actor_attempt': turn,
                        'pma_event_id': pma_upstream.last_event_id,
                        'reminder_sha256': _sha256_json(reminder),
                        'input_sent': False,
                    })
                    if event:
                        _register_pending_pma_reminder(
                            event, actor_attempt=turn,
                            pma_event_id=pma_upstream.last_event_id)
        _hook('llm_before', locals())
        if stateful is not None:
            response_gen = stateful.chat(client, messages, tools_schema, turn)
        elif pos is not None:
            if complement:
                panel = pos.exchange('decision_panel', observation=pos_observation)
                response_gen = client.chat(messages=messages, tools=tools_schema,
                                           system_overlay=panel['panel'],
                                           overlay_request_byte_limit=(None if shared_view
                                               else 90000))
            else:
                consume_current = getattr(handler, 'consume_pos_current_instruction', None)
                if consume_current is not None:
                    current_instruction = consume_current()
                    if current_instruction:
                        current_correction = ('\n\n'.join(filter(None,
                            (current_correction, current_instruction))))
                view = pos.exchange('decision_view', observation=pos_observation,
                                    actions=tools_schema,
                                    runtime_constraints=current_correction)
                request_view = {'system': system_prompt + '\n\n' + view['system'],
                                'user': view['user']}
                response_gen = client.chat(messages=messages, tools=tools_schema,
                                           request_view=request_view)
        else:
            response_gen = client.chat(messages=messages, tools=tools_schema)
        complete_policy = bool(getattr(getattr(client, 'backend', None),
                                       'task_complete_response', False))
        try:
            if verbose:
                response = yield from response_gen
                if complete_policy and not getattr(
                        response, 'complete_response_accepted', False):
                    raise RuntimeError('Task response lacked complete-response acceptance')
                yield '\n\n'
            else:
                response = exhaust(response_gen)
                if complete_policy and not getattr(
                        response, 'complete_response_accepted', False):
                    raise RuntimeError('Task response lacked complete-response acceptance')
                cleaned = _clean_content(response.content)
                if cleaned: yield cleaned + '\n'
        except ProviderResponseCancelled:
            try: response_gen.close()
            except Exception: pass
            yield "\n[Task Agent response interrupted for monitor correction.]\n"
            if stateful is not None:
                stateful.finish({'result': 'TASK_RESPONSE_CANCELLED', 'turn': turn})
                raise
            if pma_upstream is not None:
                pma_upstream.actor_step(turn, status='provider_cancelled')
            if pos is not None:
                pos.exchange('finish', reason='provider_cancelled')
                pos.close()
                raise
            messages = [{
                "role": "user",
                "content": "The previous response was interrupted before it became an accepted action.",
            }]
            continue
        except BaseException:
            if stateful is not None:
                stateful.finish({'result': 'PROVIDER_OR_CAPTURE_FAILURE',
                                 'turn': turn})
            if pos is not None:
                try: pos.exchange('finish', reason='provider_or_capture_failure')
                finally: pos.close()
            raise
        _hook('llm_after', locals())

        provider_link = _consume_provider_call() if _telemetry_enabled() else None
        if complement:
            # Complete Task acceptance is a conservative delivery boundary;
            # merely preparing a panel cannot produce revisable advice.
            delivery_id = ((provider_link or {}).get('llm_call_id') or
                f'accepted-turn-{turn}-{_sha256_json(response.content or "")}')
            pos.exchange('request_accepted', panel=panel, event_id=delivery_id)
        if provider_link:
            _research_emit('action_selected', {
                'provider_request_event_id': provider_link.get('provider_request_event_id'),
                'intervention_event_id': provider_link.get('intervention_event_id'),
                'injection_occurrence_id': provider_link.get('injection_occurrence_id'),
                'tool_names': [tc.function.name for tc in response.tool_calls],
                'tool_call_ids': [tc.id for tc in response.tool_calls],
                'response_sha256': __import__('hashlib').sha256((response.content or '').encode('utf-8')).hexdigest(),
            }, llm_call_id=provider_link['llm_call_id'], internal_turn=turn,
               parent_event_id=provider_link.get('provider_request_event_id'))

        # Expose an announced intent/tool choice to the concurrent monitor as
        # soon as it becomes public. Publishing is non-blocking: ordinary tools
        # continue immediately, while any resulting correction is delivered at
        # the next safe pre-inference boundary.
        monitor_runtime = getattr(handler.parent, 'monitor_runtime', None)
        if monitor_runtime is not None and response.tool_calls:
            monitor_runtime.archive_boundary({
                'boundary': 'post_model_pre_tool', 'internal_turn': turn,
                'response_content': response.content,
                'tool_calls': [{
                    'tool_name': call.function.name,
                    'args': json.loads(call.function.arguments),
                    'id': call.id,
                } for call in response.tool_calls],
                'tool_results': [],
            })

        completion_decision = None
        provider_error_response = (False if complete_policy
            else _is_provider_error_response(response))
        if not response.tool_calls and not provider_error_response:
            if (_telemetry_enabled() or hasattr(handler, 'completion_gate') or
                    getattr(handler.parent, 'completion_decision_callback', None) is not None):
                completion_proposal = CompletionProposal.from_response(response, turn)
                _research_emit('completion_proposal', completion_proposal.as_payload(), internal_turn=turn)
                completion_gate = getattr(handler, 'completion_gate', None)
                prepare_completion = getattr(completion_gate, 'prepare', None)
                if prepare_completion is not None:
                    prepare_completion(completion_proposal)
                checkpoint_callback = getattr(handler.parent, 'completion_proposal_checkpoint_callback', None)
                if checkpoint_callback is not None:
                    checkpoint_callback(completion_proposal, turn, provider_link)
                decision_callback = getattr(
                    handler.parent, 'completion_decision_callback', None
                )
                completion_decision = None
                if decision_callback is not None:
                    parameters = inspect.signature(decision_callback).parameters
                    if len(parameters) >= 4:
                        completion_decision = decision_callback(
                            completion_proposal, turn, provider_link, response.content
                        )
                    else:
                        completion_decision = decision_callback(
                            completion_proposal, turn, provider_link
                        )
                if completion_decision is None:
                    completion_decision = decide_completion(handler, completion_proposal)
                _research_emit('completion_decision', {
                    **completion_decision.as_payload(), 'proposal_id': completion_proposal.proposal_id
                }, internal_turn=turn)
            tool_calls = [{'tool_name': 'no_tool', 'args': {}}]
        else: tool_calls = [{'tool_name': tc.function.name, 'args': json.loads(tc.function.arguments), 'id': tc.id}
                          for tc in response.tool_calls]

        pos_actions = ([{'id': call.get('id', ''), 'name': call['tool_name'],
                         'arguments': dict(call['args']), 'order': index,
                         'status': 'not_executed'}
                        for index, call in enumerate(tool_calls)
                        if call['tool_name'] != 'no_tool'] if pos is not None else None)
        stateful_actions = ([{'id': call.get('id', ''), 'name': call['tool_name'],
            'arguments': dict(call['args'])} for call in tool_calls
            if call['tool_name'] != 'no_tool'] if stateful is not None else None)
        if pos is not None:
            pos_record('decision_selected', {'turn': turn,
                'content': response.content or '', 'actions': pos_actions,
                'provider_error': provider_error_response})
       
        tool_results = []; pos_receipts = []; stateful_receipts = []
        stateful_batch_incomplete = False
        next_prompts = set(); exit_reason = {}
        for ii, tc in enumerate(tool_calls):
            tool_name, args, tid = tc['tool_name'], tc['args'], tc.get('id', '')
            interruption = getattr(handler.parent, 'resumable_interruption', None)
            barrier = getattr(handler.parent, 'monitor_correction_barrier', None)
            if ((interruption is not None and interruption.is_requested()) or
                    (barrier is not None and barrier.is_active())):
                if stateful is not None and stateful_actions:
                    stateful.record_incomplete(turn, 'cancelled_before_execution',
                        stateful_actions, stateful_receipts,
                        not_executed_ids=[item['id'] for item in
                                          stateful_actions[len(stateful_receipts):]],
                        terminal={'result': 'CANCELLED_BEFORE_EXECUTION'})
                    stateful_batch_incomplete = True
                if pos_actions is not None:
                    for item in pos_actions[ii:]: item['status'] = 'cancelled'
                for pending in tool_calls[ii:]:
                    pending_id = pending.get('id', '')
                    if pending_id:
                        tool_results.append({
                            'tool_use_id': pending_id,
                            'content': '[Cancelled before execution for monitor correction]',
                        })
                next_prompts.add('[Current action cancelled for monitor correction]')
                break
            if tool_name == 'no_tool': pass
            else: 
                if verbose: yield f"🛠️ Tool: `{tool_name}`  📥 args:\n````text\n{get_pretty_json(args)}\n````\n"
                else: yield f"🛠️ {tool_name}({_compact_tool_args(tool_name, args)})\n\n\n"
            handler.current_turn = turn
            if pos_actions is not None and tool_name != 'no_tool':
                pos_actions[ii]['status'] = 'started'
                pos_record('tool_started', {'turn': turn, 'id': tid,
                    'name': tool_name, 'order': ii, 'arguments': pos_actions[ii]['arguments']})
            if tool_name == 'no_tool' and completion_decision and completion_decision.decision not in ('ALLOW_COMPLETE', 'ERROR_FAIL_OPEN'):
                outcome = StepOutcome(None, next_prompt=completion_decision.next_prompt,
                                      should_exit=completion_decision.decision in ('ABSTAIN', 'ERROR_FAIL_CLOSED'))
            else:
                gen = handler.dispatch(tool_name, args, response, index=ii, tool_num=len(tool_calls))
                try:
                    v = next(gen)
                    def proxy(): yield v; return (yield from gen)
                    if verbose: yield '`````\n'
                    outcome = (yield from proxy()) if verbose else exhaust(proxy())
                    if verbose: yield '`````\n'
                except StopIteration as e: outcome = e.value
                except BaseException as error:
                    if stateful is not None and tool_name != 'no_tool':
                        try:
                            stateful.record_incomplete(turn, 'tool_result_unknown_after_start',
                                stateful_actions, stateful_receipts,
                                started_unknown_ids=[tid],
                                not_executed_ids=[item['id'] for item in
                                    stateful_actions[len(stateful_receipts) + 1:]],
                                error_type=type(error).__name__,
                                error_message=str(error))
                        except BaseException:
                            pass  # Never replace the original tool exception.
                    if pos is not None and tool_name != 'no_tool':
                        pos_record('tool_result_unknown_after_start', {
                            'turn': turn, 'id': tid, 'name': tool_name,
                            'error_type': type(error).__name__, 'error': str(error)})
                    raise
            if pos_actions is not None and tool_name != 'no_tool':
                pos_actions[ii]['status'] = ('rejected' if tool_name == 'bad_json' or
                    not hasattr(handler, 'do_' + tool_name) else 'executed')
                if outcome.should_exit:
                    exit_reason = {'result': 'EXITED', 'data': outcome.data}
                elif not outcome.next_prompt:
                    exit_reason = {'result': 'CURRENT_TASK_DONE', 'data': outcome.data}
                receipt = {'tool_use_id': tid, 'name': tool_name,
                           'status': pos_actions[ii]['status'],
                           'result': _pos_public_value(outcome.data),
                           'next_prompt': outcome.next_prompt}
                pos_receipts.append(receipt)
                pos_record('tool_outcome', {'turn': turn, **receipt})
            if stateful is not None and tool_name != 'no_tool':
                stateful_receipts.append({'tool_use_id': tid,
                    'status': ('rejected' if tool_name == 'bad_json' or
                               not hasattr(handler, 'do_' + tool_name) else 'executed'),
                    'result': _pos_public_value(outcome.data)})
            
            if outcome.data is not None and tool_name != 'no_tool':
                handler.observe_tool_outcome(outcome.data, turn)
            if outcome.should_exit: 
                exit_reason = {'result': 'EXITED', 'data': outcome.data}; break
            if not outcome.next_prompt: 
                exit_reason = {'result': 'CURRENT_TASK_DONE', 'data': outcome.data}; break
            if outcome.next_prompt.startswith('未知工具'): client.last_tools = ''
            if outcome.data is not None and tool_name != 'no_tool':
                datastr = json.dumps(outcome.data, ensure_ascii=False, default=json_default) if type(outcome.data) in [dict, list] else str(outcome.data) 
                tool_results.append({'tool_use_id': tid, 'content': datastr})
            next_prompts.add(outcome.next_prompt)
        if stateful is not None:
            stateful.record_report(turn, response.content or '')
            if stateful_actions and not stateful_batch_incomplete and \
                    len(stateful_receipts) != len(stateful_actions):
                stateful.record_incomplete(turn, 'early_terminal_before_batch_complete',
                    stateful_actions, stateful_receipts,
                    not_executed_ids=[item['id'] for item in
                                      stateful_actions[len(stateful_receipts):]],
                    terminal=_pos_public_value(exit_reason))
                stateful_batch_incomplete = True
            if stateful_actions and not stateful_batch_incomplete:
                stateful.complete_batch(turn, stateful_actions, stateful_receipts)
        if pos is not None:
            pos_record('decision_batch_completed', {'turn': turn,
                'actions': pos_actions, 'tool_results': pos_receipts,
                'host_exit_reason': _pos_public_value(exit_reason)})
            try:
                pos.exchange('decision_completed', turn=turn,
                             action_count=len(pos_actions or []))
            except BaseException as error:
                if not exit_reason:
                    raise
                if complement:
                    pos_auxiliary_errors.append({'kind': 'terminal_decision_receipt',
                                                 'error_type': type(error).__name__})
                _research_emit('pos_terminal_context_error', {
                    'host_terminal': exit_reason, 'error_type': type(error).__name__,
                    'error': str(error)}, internal_turn=turn)
                pos.close()
        if len(next_prompts) == 0 or exit_reason:
            if len(handler._done_hooks) == 0 or exit_reason.get('result', '') == 'EXITED':
                if pos is not None:
                    terminal_observation = _pos_terminal_observation(
                        turn, response, pos_receipts,
                        exit_reason or {'result': 'CURRENT_TASK_DONE'})
                    try:
                        if pos.closed:
                            raise RuntimeError('PoS decision receipt unavailable')
                        if pos_actions and any(a['status'] == 'executed' for a in pos_actions):
                            extra = ({'actor_attempt': turn,
                                      'transition_id': f'actor-transition-{turn}',
                                      'source_events': [
                                          {'origin': 'GA_tool_outcome', 'turn': turn,
                                           'tool_use_id': receipt['tool_use_id'],
                                           'status': receipt['status'],
                                           'result': receipt['result']}
                                          for receipt in pos_receipts]
                                      } if complement else {})
                            pos.exchange('update', thought=response.content or '',
                                action_batch=pos_actions, observation=terminal_observation,
                                done=True, **extra)
                        pos.exchange('finish', reason=('PROVIDER_FAILURE' if
                                     provider_error_response else (exit_reason or
                                     {'result': 'CURRENT_TASK_DONE'})['result']),
                                     observation=terminal_observation)
                    except BaseException as error:
                        if complement:
                            pos_auxiliary_errors.append({'kind': 'terminal_auxiliary_update_or_finish',
                                                         'error_type': type(error).__name__})
                        _research_emit('pos_terminal_context_error', {
                            'host_terminal': exit_reason or {'result': 'CURRENT_TASK_DONE'},
                            'error_type': type(error).__name__, 'error': str(error)},
                            internal_turn=turn)
                    finally:
                        try:
                            pos.close()
                        except BaseException as error:
                            if not complement:
                                raise
                            pos_auxiliary_errors.append({'kind': 'terminal_auxiliary_close',
                                                         'error_type': type(error).__name__})
                if pma_upstream is not None:
                    pma_upstream.actor_step(
                        turn, status='completed', response=response.content or '',
                        commands=[json.dumps(call, ensure_ascii=False, default=json_default)
                                  for call in tool_calls])
                break
            next_prompts.add(handler._done_hooks.pop(0))
        next_prompt = handler.turn_end_callback(response, tool_calls, tool_results, turn, '\n'.join(next_prompts), exit_reason)
        if pos is not None:
            pos_observation = json.dumps({
                'source': 'GA_completed_joint_action', 'turn': turn,
                'tool_results': pos_receipts,
                'current_runtime_instructions': next_prompt,
                'response_content': response.content or '',
                'exit_reason': exit_reason}, ensure_ascii=False, default=json_default)
            if pos_actions and any(a['status'] == 'executed' for a in pos_actions):
                extra = ({'actor_attempt': turn,
                          'transition_id': f'actor-transition-{turn}',
                          'source_events': [
                              {'origin': 'GA_tool_outcome', 'turn': turn,
                               'tool_use_id': receipt['tool_use_id'],
                               'status': receipt['status'],
                               'result': receipt['result']}
                              for receipt in pos_receipts]
                          } if complement else {})
                pos.exchange('update', thought=response.content or '',
                             action_batch=pos_actions, observation=pos_observation,
                             done=False, **extra)
        _hook('turn_after', locals())
        if pma is not None:
            pma.observe(response.content or '',
                        [json.dumps(call, ensure_ascii=False, default=json_default) for call in tool_calls],
                        json.dumps({'content': next_prompt, 'tool_results': tool_results},
                                   ensure_ascii=False, default=json_default))
        if pma_upstream is not None:
            step_status = ('provider_cancelled' if provider_error_response else
                           'parse_error' if any(call['tool_name'] == 'bad_json'
                                                for call in tool_calls) else 'normal')
            pma_upstream.actor_step(
                turn, status=step_status, response=response.content or '',
                commands=[json.dumps(call, ensure_ascii=False, default=json_default)
                          for call in tool_calls],
                observation=json.dumps({'content': next_prompt, 'tool_results': tool_results},
                                       ensure_ascii=False, default=json_default),
                request_event_id=(provider_link or {}).get('provider_request_event_id'))
        messages = [{"role": "user", "content": next_prompt, "tool_results": tool_results}]   # just new message, history is kept in *Session
    if exit_reason: handler.turn_end_callback(response, tool_calls, tool_results, turn, '', exit_reason)
    final_outcome = exit_reason or {'result': 'MAX_TURNS_EXCEEDED'}
    if response is not None and not (complete_policy and getattr(
            response, 'complete_response_accepted', False)) and _is_provider_error_response(response):
        final_outcome = {'result': 'PROVIDER_FAILURE', 'error': response.content}
    if pos is not None and not pos.closed:
        try:
            pos.exchange('finish', reason=final_outcome['result'],
                         observation=pos_observation)
        except BaseException as error:
            if not complement:
                raise
            pos_auxiliary_errors.append({'kind': 'final_auxiliary_finish',
                                         'error_type': type(error).__name__})
        finally:
            try:
                pos.close()
            except BaseException as error:
                if not complement:
                    raise
                pos_auxiliary_errors.append({'kind': 'final_auxiliary_close',
                                             'error_type': type(error).__name__})
    if pos is not None and pos_auxiliary_errors:
        final_outcome = {**final_outcome, 'pos_archive_incomplete': True,
                         'pos_auxiliary_errors': pos_auxiliary_errors}
    if stateful is not None:
        handler.parent.stateful_finalization = stateful.finish(
            _pos_public_value(final_outcome))
    _research_emit('termination', final_outcome, internal_turn=turn)
    _hook('agent_after', locals())
    return final_outcome


def agent_runner_loop(client, system_prompt, user_input, handler, tools_schema,
                      max_turns=40, verbose=True, initial_user_content=None,
                      yield_info=False, turn_offset=0):
    """Keep PoS request scope and worker ownership even on generator close."""
    parent = handler.parent
    enabled = os.environ.get('GA_POS_ENABLED') == '1'
    stateful_enabled = os.environ.get('GA_STATEFUL_MEMORY_ENABLED') == '1'
    sentinel = object()
    old_context = getattr(parent, 'pos_decision_context', sentinel)
    old_bridge = getattr(parent, '_pos_bridge', sentinel)
    old_stateful = getattr(parent, '_stateful_memory_bridge', sentinel)
    try:
        return (yield from _agent_runner_loop_impl(
            client, system_prompt, user_input, handler, tools_schema,
            max_turns=max_turns, verbose=verbose,
            initial_user_content=initial_user_content, yield_info=yield_info,
            turn_offset=turn_offset))
    finally:
        if stateful_enabled:
            bridge = getattr(parent, '_stateful_memory_bridge', None)
            if bridge is not None and bridge is not old_stateful:
                if sys.exc_info()[0] is not None:
                    try:
                        parent.stateful_finalization = bridge.finish(
                            {'result': 'GENERATOR_CLOSED_OR_FAILED'})
                    except BaseException: pass  # Preserve the original failure.
                else:
                    parent.stateful_finalization = bridge.finish(
                        {'result': 'GENERATOR_CLOSED_OR_FAILED'})
            if old_stateful is sentinel:
                if hasattr(parent, '_stateful_memory_bridge'):
                    delattr(parent, '_stateful_memory_bridge')
            else:
                parent._stateful_memory_bridge = old_stateful
        if enabled:
            bridge = getattr(parent, '_pos_bridge', None)
            if bridge is not None and bridge is not old_bridge:
                try:
                    if not bridge.closed and bridge.process.poll() is None:
                        try: bridge.exchange('abort', reason='generator_closed_or_failed')
                        except BaseException: pass
                finally:
                    bridge.close()
            for name, previous in (('pos_decision_context', old_context),
                                   ('_pos_bridge', old_bridge)):
                if previous is sentinel:
                    if hasattr(parent, name): delattr(parent, name)
                else:
                    setattr(parent, name, previous)

def _clean_content(text):
    if not text: return ''
    def _shrink_code(m):
        lines = m.group(0).split('\n')
        lang = lines[0].replace('```','').strip()
        body = [l for l in lines[1:-1] if l.strip()]
        if len(body) <= 6: return m.group(0)
        preview = '\n'.join(body[:5])
        return f'```{lang}\n{preview}\n  ... ({len(body)} lines)\n```'
    text = re.sub(r'```[\s\S]*?```', _shrink_code, text)
    for p in [r'<file_content>[\s\S]*?</file_content>', r'<tool_(?:use|call)>[\s\S]*?</tool_(?:use|call)>', r'(\r?\n){3,}']:
        text = re.sub(p, '\n\n' if '\\n' in p else '', text)
    return text.strip()

def _is_provider_error_response(response):
    """Keep provider transport sentinels out of the semantic completion path."""
    content = (getattr(response, 'content', '') or '').strip()
    return content.startswith(('!!!Error:', '[Error:')) or '[!!! 流异常中断' in content[-160:]

def _compact_tool_args(name, args):
    a = {k: v for k, v in args.items() if k != '_index'}
    for k in ('path',): 
        if k in a: a[k] = os.path.basename(a[k])
    if name == 'update_working_checkpoint': s = a.get('key_info', ''); return (s[:60]+'...') if len(s)>60 else s
    if name == 'ask_user':
        q = str(a.get('question', ''))
        cs = a.get('candidates') or []
        if cs: q += '\ncandidates:\n' + '\n'.join(f'- {c}' for c in cs)
        return q
    s = json.dumps(a, ensure_ascii=False); return (s[:120]+'...') if len(s)>120 else s
