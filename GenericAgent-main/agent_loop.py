import inspect, json, re, os
from dataclasses import dataclass
from typing import Any, Optional
from research_runtime import CompletionProposal, decide_completion, emit as _research_emit, telemetry_enabled as _telemetry_enabled, consume_provider_call as _consume_provider_call
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
def exhaust(g):
    try: 
        while True: next(g)
    except StopIteration as e: return e.value

def get_pretty_json(data):
    if isinstance(data, dict) and "script" in data:
        data = data.copy(); data["script"] = data["script"].replace("; ", ";\n  ")
    return json.dumps(data, indent=2, ensure_ascii=False).replace('\\n', '\n')

def agent_runner_loop(client, system_prompt, user_input, handler, tools_schema, 
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
    if os.environ.get('GA_PMA_ENABLED') == '1':
        from pma_baseline.runtime import from_environment
        pma = from_environment(initial_content)
    while local_turn < handler.max_turns:
        local_turn += 1; turn = int(turn_offset) + local_turn
        consume_resume = getattr(handler.parent, 'consume_resumable_interruption', None)
        if consume_resume is not None:
            resumed = consume_resume()
            if resumed:
                injection = "\n\n".join(
                    f"[MONITOR CORRECTION]\n{item['message']}" for item in resumed
                )
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
                messages.append({'role': 'user', 'content': reminder})
        _hook('llm_before', locals())
        response_gen = client.chat(messages=messages, tools=tools_schema)
        try:
            if verbose:
                response = yield from response_gen
                yield '\n\n'
            else:
                response = exhaust(response_gen)
                cleaned = _clean_content(response.content)
                if cleaned: yield cleaned + '\n'
        except ProviderResponseCancelled:
            try: response_gen.close()
            except Exception: pass
            yield "\n[Task Agent response interrupted for monitor correction.]\n"
            messages = [{
                "role": "user",
                "content": "The previous response was interrupted before it became an accepted action.",
            }]
            continue
        _hook('llm_after', locals())

        provider_link = _consume_provider_call() if _telemetry_enabled() else None
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
        provider_error_response = _is_provider_error_response(response)
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
       
        tool_results = []; next_prompts = set(); exit_reason = {}
        for ii, tc in enumerate(tool_calls):
            tool_name, args, tid = tc['tool_name'], tc['args'], tc.get('id', '')
            interruption = getattr(handler.parent, 'resumable_interruption', None)
            if interruption is not None and interruption.is_requested():
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
        if len(next_prompts) == 0 or exit_reason:
            if len(handler._done_hooks) == 0 or exit_reason.get('result', '') == 'EXITED': break
            next_prompts.add(handler._done_hooks.pop(0))
        next_prompt = handler.turn_end_callback(response, tool_calls, tool_results, turn, '\n'.join(next_prompts), exit_reason)
        _hook('turn_after', locals())
        if pma is not None:
            pma.observe(response.content or '',
                        [json.dumps(call, ensure_ascii=False, default=json_default) for call in tool_calls],
                        json.dumps(tool_results, ensure_ascii=False, default=json_default))
        messages = [{"role": "user", "content": next_prompt, "tool_results": tool_results}]   # just new message, history is kept in *Session
    if exit_reason: handler.turn_end_callback(response, tool_calls, tool_results, turn, '', exit_reason)
    final_outcome = exit_reason or {'result': 'MAX_TURNS_EXCEEDED'}
    if response is not None and _is_provider_error_response(response):
        final_outcome = {'result': 'PROVIDER_FAILURE', 'error': response.content}
    _research_emit('termination', final_outcome, internal_turn=turn)
    _hook('agent_after', locals())
    return final_outcome

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
