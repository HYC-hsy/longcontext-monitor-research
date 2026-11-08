"""GA history functions copied verbatim from GenericAgent-main/llmcore.py.

This host-side copy avoids importing the task-container runtime. Behavioral
parity against the pinned GA source is tested. Telemetry is not emitted here.
"""
import copy
import json
import re

def _telemetry_enabled():
    return False

def _history_bytes(messages):
    """Count GPT opaque reasoning once, not its duplicate visible output.

    The Responses output mirror is needed for stateless continuation. Its
    message and function-call items duplicate the GA-visible content already
    counted in each history row; reasoning items have no visible counterpart.
    """
    rows = []
    for message in messages:
        row = {key: value for key, value in message.items()
               if key != '_openai_output_items'}
        opaque = message.get('_openai_output_items') or []
        reasoning = [item for item in opaque if isinstance(item, dict)
                     and item.get('type') == 'reasoning']
        if reasoning:
            row['_openai_reasoning_budget'] = reasoning
        rows.append(row)
    return sum(len(json.dumps(row, ensure_ascii=False)) for row in rows)

def compress_history_tags(messages, keep_recent=10, max_len=800, force=False, interval=5):
    """Compress <thinking>/<tool_use>/<tool_result> tags in older messages to save tokens."""
    compress_history_tags._cd = getattr(compress_history_tags, '_cd', 0) + 1
    if force: compress_history_tags._cd = 0
    if compress_history_tags._cd % interval != 0: return messages
    _before = _history_bytes(messages)
    _pats = {tag: re.compile(rf'(<{tag}>)([\s\S]*?)(</{tag}>)') for tag in ('thinking', 'think', 'tool_use', 'tool_result')}
    _hist_pat = re.compile(r'<(history|key_info|earlier_context)>[\s\S]*?</\1>')
    def _trunc_str(s): return s[:max_len//2] + '\n...[Truncated]...\n' + s[-max_len//2:] if isinstance(s, str) and len(s) > max_len else s
    def _trunc(text):
        text = _hist_pat.sub(lambda m: f'<{m.group(1)}>[...]</{m.group(1)}>', text)
        for pat in _pats.values(): text = pat.sub(lambda m: m.group(1) + _trunc_str(m.group(2)) + m.group(3), text)
        return text
    for i, msg in enumerate(messages):
        if i >= len(messages) - keep_recent: break
        c = msg['content']
        if isinstance(c, str): msg['content'] = _trunc(c)
        elif isinstance(c, list):
            for b in c:
                if not isinstance(b, dict): continue
                t = b.get('type')
                if t == 'text' and isinstance(b.get('text'), str): b['text'] = _trunc(b['text'])
                elif t == 'thinking' and isinstance(b.get('thinking'), str): b['thinking'] = _trunc_str(b['thinking'])
                elif t == 'tool_result':
                    tc = b.get('content')
                    if isinstance(tc, str): b['content'] = _trunc_str(tc)
                    elif isinstance(tc, list):
                        for sub in tc:
                            if isinstance(sub, dict) and sub.get('type') == 'text': sub['text'] = _trunc_str(sub.get('text'))
                elif t == 'tool_use' and isinstance(b.get('input'), dict):
                    for k, v in b['input'].items(): b['input'][k] = _trunc_str(v)
    print(f"[Cut] {_before} -> {_history_bytes(messages)}")
    return messages

def _sanitize_leading_user_msg(msg):
    """把 user 消息里的 tool_result 块改写成纯文本，避免孤立引用。
    history 统一使用 Claude content-block 格式：content 是 list of blocks。"""
    msg = dict(msg)  # 浅拷贝外层 dict
    content = msg.get('content')
    if not isinstance(content, list): return msg
    texts = []
    for block in content:
        if not isinstance(block, dict): continue
        if block.get('type') == 'tool_result':
            c = block.get('content', '')
            if isinstance(c, list):  # content 本身也可能是 list[{type:text,text:...}]
                texts.extend(b.get('text', '') for b in c if isinstance(b, dict))
            else: texts.append(str(c))
        elif block.get('type') == 'text': texts.append(block.get('text', ''))
    msg['content'] = [{"type": "text", "text": '\n'.join(t for t in texts if t)}]
    return msg

def trim_messages_history(history, sess):
    observing = _telemetry_enabled()
    if observing:
        transform_id = _research_id('history')
        before = {'message_count': len(history), 'bytes': sum(len(json.dumps(m, ensure_ascii=False)) for m in history),
                  'sha256': _sha256_json(history)}
        _research_emit('history_transform_started', before, history_transform_id=transform_id)
    cap = sess.context_win * 3
    target = int(cap * getattr(sess, 'trim_keep_rate', 0.6))
    def cost(): return _history_bytes(history)
    compress_history_tags(history, interval=getattr(sess, 'cut_msg_interval', 5))
    print(f'[Debug] Current context: {cost()} chars, {len(history)} messages.')
    if cost() <= cap:
        if observing:
            after = {'message_count': len(history), 'bytes': cost(), 'sha256': _sha256_json(history)}
            _research_emit('history_transform_finished', {**after, 'changed': after['sha256'] != before['sha256']}, history_transform_id=transform_id)
        return
    compress_history_tags(history, keep_recent=4, force=True)
    if cost() <= target:
        if observing:
            after = {'message_count': len(history), 'bytes': cost(), 'sha256': _sha256_json(history)}
            _research_emit('history_transform_finished', {**after, 'changed': after['sha256'] != before['sha256']}, history_transform_id=transform_id)
        return
    while len(history) > 9 and cost() > target:
        history.pop(0)
        while history and history[0].get('role') != 'user': history.pop(0)
        if history and history[0].get('role') == 'user': history[0] = _sanitize_leading_user_msg(history[0])
    print(f'[Debug] Trimmed context, current: {cost()} chars, {len(history)} messages.')
    if observing:
        after = {'message_count': len(history), 'bytes': cost(), 'sha256': _sha256_json(history)}
        _research_emit('history_transform_finished', {**after, 'changed': after['sha256'] != before['sha256'],
                       'removed_messages': before['message_count'] - after['message_count']}, history_transform_id=transform_id)

def _msgs_claude2oai(messages):
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        blocks = content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
        if role == "assistant":
            text_parts, tool_calls, reasoning = [], [], ""
            for b in blocks:
                if not isinstance(b, dict): continue
                if b.get("type") == "thinking" and b.get("thinking"): reasoning = b["thinking"]
                elif b.get("type") == "text" and b.get("text"): text_parts.append({"type": "text", "text": b.get("text", "")})
                elif b.get("type") == "tool_use":
                    tool_calls.append({
                        "id": b.get("id") or '', "type": "function",
                        "function": {"name": b.get("name", ""), "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
                    })
            m = {"role": "assistant"}
            if reasoning: m["reasoning_content"] = reasoning
            if text_parts: m["content"] = text_parts
            elif not tool_calls: m["content"] = "."
            if tool_calls: m["tool_calls"] = tool_calls
            result.append(m)
        elif role == "user":
            text_parts = []
            for b in blocks:
                if not isinstance(b, dict): continue
                if b.get("type") == "tool_result":
                    if text_parts:
                        result.append({"role": "user", "content": text_parts})
                        text_parts = []
                    tr = b.get("content", "")
                    if isinstance(tr, list):
                        tr = "\n".join(x.get("text", "") for x in tr if isinstance(x, dict) and x.get("type") == "text")
                    result.append({"role": "tool", "tool_call_id": b.get("tool_use_id") or '', "content": tr if isinstance(tr, str) else str(tr)})
                elif b.get("type") == "image":
                    src = b.get("source") or {}
                    if src.get("type") == "base64" and src.get("data"):
                        text_parts.append({"type": "image_url", "image_url": {"url": f"data:{src.get('media_type', 'image/png')};base64,{src.get('data', '')}"}})
                elif b.get("type") == "image_url": text_parts.append(b)
                elif b.get("type") == "text" and b.get("text"): text_parts.append({"type": "text", "text": b.get("text", "")})
            if text_parts: result.append({"role": "user", "content": text_parts})
        else: result.append(msg)
    return result

class GAHistoryIntegrityError(BaseException):
    """Cannot faithfully continue the provider's model/tool history."""

class GAHistoryConfig:
    # BaseSession defaults for non-DeepSeek models.
    context_win = 30000
    trim_keep_rate = 0.6
    cut_msg_interval = 5

def prepare_history(history, prompt):
    # GA places prior tool results and the next user text in one user turn.
    text_block = {"type": "text", "text": prompt}
    if (history and history[-1].get("role") == "user" and
            isinstance(history[-1].get("content"), list) and
            any(b.get("type") == "tool_result" for b in history[-1]["content"]
                if isinstance(b, dict))):
        history[-1]["content"].append(text_block)
    else:
        history.append({"role": "user", "content": [text_block]})
    trim_messages_history(history, GAHistoryConfig())
    current = history[-1]
    if current.get("role") != "user" or current.get("content", [])[-1:] != [text_block]:
        raise GAHistoryIntegrityError("GA trimming unexpectedly changed the current PMA prompt")
    # LiteLLM appends the current prompt itself; preserve only prior tool results.
    prior = copy.deepcopy(history)
    prior[-1]["content"].pop()
    if not prior[-1]["content"]:
        prior.pop()
    # Preserve provider-issued signed thinking blocks as opaque metadata.
    # GA's trimmer only modifies content; it must not corrupt signatures.
    result = []
    for message in prior:
        converted = _msgs_claude2oai([message])
        blocks = message.get("_provider_thinking_blocks")
        if blocks:
            if len(converted) != 1 or converted[0].get("role") != "assistant":
                raise GAHistoryIntegrityError("cannot associate signed provider blocks")
            converted[0]["thinking_blocks"] = copy.deepcopy(blocks)
        output_items = message.get("_openai_output_items")
        if output_items:
            if len(converted) != 1 or converted[0].get("role") != "assistant":
                raise GAHistoryIntegrityError("cannot associate Responses output items")
            converted[0]["_openai_output_items"] = copy.deepcopy(output_items)
        result.extend(converted)
    return result
