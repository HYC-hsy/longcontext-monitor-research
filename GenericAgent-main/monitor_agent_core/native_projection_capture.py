"""Pilot-only, pre-transport verification of native root projection lineage."""

import json

from .root_records_v1 import canonical, digest
from .root_records_native_v2 import project, validate_transform


def verify(private_root, monitor, request_id, payload):
    pending = monitor._projection_pending_request
    if pending is None:
        return None
    client = monitor.client
    if client.provider != 'anthropic' or client.pre_send_capture is None:
        raise ValueError('Native projection is restricted to the pilot Anthropic capture path')
    if monitor.completion_state() != monitor.root_frame_handoff:
        raise ValueError('Native projection handoff became stale')
    if pending['identity'] != (monitor.root_frame_handoff['request_id'],
                               monitor.root_frame_handoff['generation']):
        raise ValueError('Native projection handoff identity changed')
    if payload.get('messages') != client.history or payload.get('model') != client.model or (
            payload.get('max_tokens') != client.max_tokens or payload.get('system') != client.system):
        raise ValueError('Native projection request assembly changed')

    def read(locator):
        if not isinstance(locator, str) or not locator.startswith('monitor/audit/') or '..' in locator.split('/'):
            raise ValueError('Native projection archive locator invalid')
        return (private_root / locator[len('monitor/'):]).read_bytes()

    commit = json.loads(read(pending['commit_locator']))
    base = pending['commit_locator'].rsplit('/', 1)[0]
    source = json.loads(read(base + '/source.json'))
    projected = json.loads(read(base + '/projected_history.json'))
    manifest = json.loads(read(base + '/manifest.json'))
    recomputed, expected, _ = project(source)
    expected.update(request_id=pending['identity'][0], generation=pending['identity'][1])
    if manifest != expected or projected != recomputed or commit != {
            'request_id': pending['identity'][0], 'generation': pending['identity'][1],
            'source_sha256': expected['source_sha256'],
            'projected_sha256': expected['projected_sha256'],
            'applied': expected['applied'], 'source_locator': base + '/source.json',
    }:
        raise ValueError('Native projection archive or commit identity mismatch')
    last_captured = pending.get('last_captured_history')
    last_transform_count = pending.get('last_transform_count', 0)
    if last_captured is not None:
        previous = json.loads(read(pending['last_capture_locator']))
        prior_payload = previous['payload']
        prior_messages = json.loads(json.dumps(prior_payload['messages'], ensure_ascii=False))
        transient = pending.get('last_transient')
        if transient is not None and prior_messages[-1] == {
                'role': 'user', 'content': [{'type': 'text', 'text': transient}]}:
            prior_messages.pop()
        if (digest(canonical(prior_payload)) != pending['last_payload_sha256']
                or prior_messages != last_captured):
            raise ValueError('Prior native request capture changed')
        if len(pending['transforms']) > last_transform_count:
            next_archive = pending['transforms'][last_transform_count]['archive']
            if json.loads(read(next_archive))[:len(last_captured)] != last_captured:
                raise ValueError('Native history changed before recorded transform')
        elif payload['messages'][:len(last_captured)] != last_captured:
            raise ValueError('Native history changed after prior request')
    anchor = projected
    for transform in pending['transforms']:
        receipt = json.loads(read(transform['receipt']))
        after = json.loads(read(transform['after_locator']))
        archived = json.loads(read(transform['archive']))
        if (receipt != {key: value for key, value in transform.items()
                        if key not in ('receipt', 'after_history')}
                or after != transform['after_history'] or archived[:len(anchor)] != anchor
                or receipt['before_sha256'] != digest(canonical(archived))
                or receipt['after_sha256'] != digest(canonical(after))):
            raise ValueError('Native projection transform archive mismatch')
        validate_transform(receipt['kind'], archived, after, receipt['archive'], receipt['details'])
        anchor = after
    messages = payload['messages']
    if messages[:len(anchor)] != anchor:
        raise ValueError('Native projection lineage absent from request')
    root_input = getattr(monitor, '_projection_root_input', None)
    if not isinstance(root_input, str) or not any(
            block.get('type') == 'text' and block.get('text') == root_input
            for history in [messages] + [json.loads(read(t['archive'])) for t in pending['transforms']]
            for message in history for block in message.get('content', [])):
        raise ValueError('Current root input not shown or archived at legal cut')
    purpose = getattr(client, 'request_purpose', 'review')
    if not pending.get('verified'):
        root_suffix = [{'role': 'user', 'content': [{'type': 'text', 'text': root_input}]}]
        update = getattr(monitor, '_projection_latest_review_update', None)
        if update:
            root_suffix.append({'role': 'user', 'content': [{'type': 'text', 'text': update}]})
        if pending['transforms']:
            first_before = json.loads(read(pending['transforms'][0]['archive']))
            if first_before[len(projected):] != root_suffix:
                raise ValueError('Native pre-maintenance root input suffix changed')
            suffix = messages[len(anchor):]
        else:
            suffix = messages[len(anchor):]
            if suffix[:len(root_suffix)] != root_suffix:
                raise ValueError('Native current root input suffix changed')
            suffix = suffix[len(root_suffix):]
        expected_suffix = []
        if purpose in ('continuation', 'format_repair'):
            expected_suffix.append({'role': 'user', 'content': [
                {'type': 'text', 'text': getattr(client, 'maintenance_prompt', None)}]})
        elif getattr(client, 'request_local_context', None):
            expected_suffix.append({'role': 'user', 'content': [
                {'type': 'text', 'text': client.request_local_context}]})
        if suffix != expected_suffix:
            raise ValueError('Native request contains an unaccounted initial suffix')
    if purpose == 'review':
        if payload.get('system') != monitor._projection_root_system or (
                payload.get('tools') != monitor._projection_root_tools):
            raise ValueError('Native root review system or tools changed')
        context = getattr(client, 'request_local_context', None)
        if context and messages[-1] != {'role': 'user', 'content': [{'type': 'text', 'text': context}]}:
            raise ValueError('Native request-local context changed')
        pending['request_id'] = request_id
    elif purpose in ('continuation', 'format_repair'):
        if payload.get('tools') != [] or not isinstance(getattr(client, 'maintenance_prompt', None), str):
            raise ValueError('Native maintenance input or tools changed')
        if not any(block.get('text') == client.maintenance_prompt
                   for message in messages for block in message.get('content', [])):
            raise ValueError('Native maintenance prompt absent')
    else:
        raise ValueError('Unsupported native projection request purpose')
    return {'commit': pending['commit_locator'], 'source_sha256': expected['source_sha256'],
            'projected_sha256': expected['projected_sha256'],
            'transform_receipts': [t['receipt'] for t in pending['transforms']],
            'last_anchor_sha256': digest(canonical(anchor)), 'purpose': purpose}
