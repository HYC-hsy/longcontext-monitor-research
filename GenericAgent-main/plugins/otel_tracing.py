"""Optional OpenTelemetry tracing for GenericAgent.

Enabled only when GA_OTEL_ENABLED=1. Full prompt, response, tool arguments, and
tool results are opt-in via GA_OTEL_CAPTURE_CONTENT=1.
"""
import atexit
import hashlib
import json
import os
import threading
from pathlib import Path


_ENABLED = os.environ.get('GA_OTEL_ENABLED', '').lower() in ('1', 'true', 'yes', 'on')

if _ENABLED:
    from opentelemetry import context, trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExportResult
    from opentelemetry.trace import SpanKind, Status, StatusCode

    import plugins.hooks as hooks
    from research_runtime import OtelEventExporter, current_identity, register_exporter, unregister_exporter

    _SCHEMA_VERSION = 'ga-otel-mvp/1'
    _CAPTURE_CONTENT = os.environ.get('GA_OTEL_CAPTURE_CONTENT', '').lower() in ('1', 'true', 'yes', 'on')
    _CONTENT_LIMIT = max(256, int(os.environ.get('GA_OTEL_CONTENT_LIMIT', '20000')))
    _EXPECTED_TURNS = max(1, int(os.environ.get('GA_BENCH_EXPECTED_TURNS', '1')))
    _ENDPOINT = os.environ.get('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT', 'http://127.0.0.1:4318/v1/traces')
    _RUN_ID = os.environ.get('GA_BENCH_RUN_ID', '')
    _TASK_ID = os.environ.get('GA_BENCH_TASK_ID', '')
    _ARTIFACT_DIR = os.environ.get('GA_OTEL_ARTIFACT_DIR', '')

    _resource = Resource.create({
        'service.name': os.environ.get('OTEL_SERVICE_NAME', 'genericagent'),
        'service.version': os.environ.get('GA_VERSION', 'unknown'),
        'telemetry.schema.version': _SCHEMA_VERSION,
    })
    class _TrackingOTLPSpanExporter(OTLPSpanExporter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.attempts = 0
            self.successes = 0
            self.failures = 0

        def export(self, spans):
            self.attempts += 1
            result = super().export(spans)
            if result is SpanExportResult.SUCCESS:
                self.successes += 1
            else:
                self.failures += 1
            return result


    _provider = TracerProvider(resource=_resource)
    _exporter = _TrackingOTLPSpanExporter(endpoint=_ENDPOINT, timeout=5)
    _processor = BatchSpanProcessor(
        _exporter,
        schedule_delay_millis=200,
        max_export_batch_size=128,
        export_timeout_millis=5000,
    )
    _provider.add_span_processor(_processor)
    trace.set_tracer_provider(_provider)
    _tracer = trace.get_tracer('genericagent', _SCHEMA_VERSION)
    _tls = threading.local()


    def _common_attributes():
        identity = current_identity()
        attrs = {
            'benchmark.run.id': identity.get('run_id') or _RUN_ID or 'interactive',
            'benchmark.task.id': identity.get('task_id') or _TASK_ID or 'interactive',
            'ga.research.experiment_id': identity.get('experiment_id') or 'interactive',
            'ga.research.condition_id': identity.get('condition_id') or 'original',
            'ga.research.branch_id': identity.get('branch_id') or 'original',
            'ga.telemetry.schema_version': _SCHEMA_VERSION,
        }
        if _ARTIFACT_DIR:
            attrs['ga.artifact.directory'] = _ARTIFACT_DIR
        return attrs


    def _serialize(value):
        try:
            return json.dumps(value, ensure_ascii=False, default=str, separators=(',', ':'))
        except Exception:
            return str(value)


    def _content_attributes(prefix, value):
        text = value if isinstance(value, str) else _serialize(value)
        attrs = {
            f'{prefix}.size': len(text.encode('utf-8', errors='replace')),
            f'{prefix}.sha256': hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest(),
        }
        if _CAPTURE_CONTENT:
            attrs[f'{prefix}.content'] = text[:_CONTENT_LIMIT]
            attrs[f'{prefix}.truncated'] = len(text) > _CONTENT_LIMIT
        return attrs


    def _start_span(name, attributes, kind=SpanKind.INTERNAL):
        span = _tracer.start_span(name, kind=kind, attributes={**_common_attributes(), **attributes})
        token = context.attach(trace.set_span_in_context(span))
        return span, token


    def _end_span(span, token, error=None):
        if not span:
            return
        if error:
            span.record_exception(error)
            span.set_status(Status(StatusCode.ERROR, str(error)))
        span.end()
        if token is not None:
            context.detach(token)


    def _backend_info(client):
        backend = getattr(client, 'backend', None)
        model = str(getattr(backend, 'model', '') or 'unknown')
        backend_type = type(backend).__name__ if backend is not None else 'unknown'
        lower = backend_type.lower()
        if 'claude' in lower:
            provider = 'anthropic'
        elif any(name in lower for name in ('oai', 'openai')):
            provider = 'openai'
        else:
            provider = str(getattr(backend, 'name', '') or 'unknown')
        return backend, model, provider, backend_type


    def _ensure_task_span(ctx):
        if getattr(_tls, 'task_span', None):
            return
        client = ctx.get('client')
        _, model, _, backend_type = _backend_info(client)
        attrs = {
            'gen_ai.operation.name': 'invoke_agent',
            'gen_ai.provider.name': 'genericagent',
            'gen_ai.agent.name': 'GenericAgent',
            'gen_ai.request.model': model,
            'ga.backend.type': backend_type,
            'ga.expected_user_turns': _EXPECTED_TURNS,
        }
        _tls.task_span, _tls.task_token = _start_span('invoke_agent GenericAgent', attrs)
        _tls.trace_id = format(_tls.task_span.get_span_context().trace_id, '032x')
        _tls.completed_turns = 0
        _tls.next_turn = 0


    @hooks.register('agent_before')
    def _on_agent_before(ctx):
        _ensure_task_span(ctx)
        _tls.next_turn += 1
        user_input = ctx.get('user_input', '')
        attrs = {
            'ga.user_turn.index': _tls.next_turn,
            'ga.user_turn.source': 'agent' if getattr(ctx.get('handler', None), 'parent', None) is not None else 'unknown',
            **_content_attributes('ga.user_input', user_input),
        }
        _tls.turn_span, _tls.turn_token = _start_span(f'ga.user_turn {_tls.next_turn}', attrs)


    @hooks.register('agent_after')
    def _on_agent_after(ctx):
        exit_reason = ctx.get('exit_reason') or {}
        span = getattr(_tls, 'turn_span', None)
        if span:
            span.set_attribute('ga.agent.exit_reason', str(exit_reason.get('result', 'unknown')))
            span.set_attribute('ga.agent.internal_turns', int(ctx.get('turn', 0)))
        _end_span(span, getattr(_tls, 'turn_token', None))
        _tls.turn_span = _tls.turn_token = None
        _tls.completed_turns += 1
        if _tls.completed_turns >= _EXPECTED_TURNS:
            _finish_task()


    @hooks.register('llm_before')
    def _on_llm_before(ctx):
        client = ctx.get('client')
        _, model, provider, backend_type = _backend_info(client)
        messages = ctx.get('messages') or []
        tools = ctx.get('tools_schema') or []
        attrs = {
            'gen_ai.operation.name': 'chat',
            'gen_ai.provider.name': provider,
            'gen_ai.request.model': model,
            'ga.backend.type': backend_type,
            'ga.message.count': len(messages),
            'ga.tool.definition.count': len(tools),
            'ga.agent.internal_turn': int(ctx.get('turn', 0)),
            **_content_attributes('ga.llm.input', messages),
        }
        _tls.llm_span, _tls.llm_token = _start_span(f'chat {model}', attrs, SpanKind.CLIENT)


    @hooks.register('llm_after')
    def _on_llm_after(ctx):
        span = getattr(_tls, 'llm_span', None)
        response = ctx.get('response')
        if span:
            span.set_attribute('ga.llm.tool_call.count', len(getattr(response, 'tool_calls', None) or []))
            span.set_attribute('gen_ai.response.finish_reasons', [str(getattr(response, 'stop_reason', 'unknown'))])
            for key, value in _content_attributes('ga.llm.output', getattr(response, 'content', '')).items():
                span.set_attribute(key, value)
        _end_span(span, getattr(_tls, 'llm_token', None))
        _tls.llm_span = _tls.llm_token = None


    @hooks.register('tool_before')
    def _on_tool_before(ctx):
        name = str(ctx.get('tool_name', 'unknown'))
        if name == 'no_tool':
            return
        args = {k: v for k, v in (ctx.get('args') or {}).items() if not k.startswith('_')}
        response = ctx.get('response')
        index = int(ctx.get('index', 0))
        calls = getattr(response, 'tool_calls', None) or []
        call_id = getattr(calls[index], 'id', '') if index < len(calls) else ''
        attrs = {
            'gen_ai.operation.name': 'execute_tool',
            'gen_ai.tool.name': name,
            'gen_ai.tool.call.id': str(call_id),
            'ga.agent.internal_turn': int(getattr(ctx.get('self'), 'current_turn', 0)),
            **_content_attributes('ga.tool.arguments', args),
        }
        span, token = _start_span(f'execute_tool {name}', attrs)
        if not hasattr(_tls, 'tool_stack'):
            _tls.tool_stack = []
        _tls.tool_stack.append((span, token))


    @hooks.register('tool_after')
    def _on_tool_after(ctx):
        stack = getattr(_tls, 'tool_stack', [])
        if not stack:
            return
        span, token = stack.pop()
        result = ctx.get('ret')
        result_data = getattr(result, 'data', None)
        if span:
            span.set_attribute('ga.tool.should_exit', bool(getattr(result, 'should_exit', False)))
            for key, value in _content_attributes('ga.tool.result', result_data).items():
                span.set_attribute(key, value)
            if isinstance(result_data, dict) and result_data.get('status') == 'error':
                span.set_status(Status(StatusCode.ERROR, str(result_data.get('msg', 'tool error'))))
        _end_span(span, token)


    def record_usage(usage, api_mode):
        """Attach provider-reported usage to the current LLM span."""
        span = getattr(_tls, 'llm_span', None)
        if not span or not usage:
            return
        if api_mode == 'responses':
            inp = usage.get('input_tokens', 0)
            out = usage.get('output_tokens', 0)
            cached = (usage.get('input_tokens_details') or {}).get('cached_tokens', 0)
            created = 0
        elif api_mode == 'chat_completions':
            inp = usage.get('prompt_tokens', 0)
            out = usage.get('completion_tokens', 0)
            cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0)
            created = 0
        else:
            inp = usage.get('input_tokens', 0)
            out = usage.get('output_tokens', 0)
            cached = usage.get('cache_read_input_tokens', 0)
            created = usage.get('cache_creation_input_tokens', 0)
        span.set_attribute('gen_ai.usage.input_tokens', int(inp or 0))
        span.set_attribute('gen_ai.usage.output_tokens', int(out or 0))
        span.set_attribute('ga.usage.cache_read_input_tokens', int(cached or 0))
        span.set_attribute('ga.usage.cache_creation_input_tokens', int(created or 0))
        span.set_attribute('ga.llm.api_mode', str(api_mode))


    def _research_span(event_type):
        if event_type.startswith(('provider_', 'history_')):
            span = getattr(_tls, 'llm_span', None)
            if span is not None:
                return span
        return getattr(_tls, 'turn_span', None) or getattr(_tls, 'task_span', None)


    _research_exporter = OtelEventExporter(_research_span)
    register_exporter(_research_exporter)


    def _finish_task():
        span = getattr(_tls, 'task_span', None)
        if not span:
            return
        trace_id = getattr(_tls, 'trace_id', '')
        span.set_attribute('ga.completed_user_turns', int(getattr(_tls, 'completed_turns', 0)))
        _end_span(span, getattr(_tls, 'task_token', None))
        _tls.task_span = _tls.task_token = None
        flush_completed = bool(_provider.force_flush(timeout_millis=5000))
        if _ARTIFACT_DIR:
            path = Path(_ARTIFACT_DIR) / 'otel_trace.json'
            path.write_text(json.dumps({
                'trace_id': trace_id,
                'run_id': _RUN_ID,
                'task_id': _TASK_ID,
                'expected_user_turns': _EXPECTED_TURNS,
                'completed_user_turns': int(getattr(_tls, 'completed_turns', 0)),
                'endpoint': _ENDPOINT,
                'schema_version': _SCHEMA_VERSION,
                'force_flush_completed': flush_completed,
                'export_attempts': _exporter.attempts,
                'export_successes': _exporter.successes,
                'export_failures': _exporter.failures,
            }, ensure_ascii=False, indent=2), encoding='utf-8')
        _tls.completed_turns = 0
        _tls.next_turn = 0


    def shutdown():
        try:
            unregister_exporter(_research_exporter)
            _finish_task()
            _provider.shutdown()
        except Exception:
            pass


    atexit.register(shutdown)

else:
    def record_usage(usage, api_mode):
        return None
