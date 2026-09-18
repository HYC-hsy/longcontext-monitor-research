"""Provider transport owned by Monitor Agent; no GenericAgent dependencies."""

from __future__ import annotations

import json
import hashlib
import re
import threading
import time
import uuid
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelResponse:
    content: str
    tool_calls: list[ToolCall]
    usage: dict


class ProviderError(RuntimeError):
    pass


class RetryableProviderError(ProviderError):
    """Explicit temporary remote failure, not a model/tool decision."""


class ProviderRecoveryExhausted(ProviderError):
    """Bounded transport recovery ended; do not start another review to retry."""


class HistoryCapacityError(ProviderRecoveryExhausted):
    """Preserved history cannot fit; new wakes cannot repair this failure."""


def failure_chain(exc):
    """Never propagate arbitrary exception messages or response text as metadata."""
    chain, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        code = getattr(exc, 'code', None)
        chain.append({'type': type(exc).__name__, 'code': code if code in {
            'unexpected_tool', 'empty_note', 'reasoning_echo', 'truncated_note',
            'incomplete_stream', 'abnormal_stop'} else None})
        exc = exc.__cause__
    return chain


def is_reasoning_echo(text, blocks):
    """Detect a transport-level duplicate, not the quality/style of a note."""
    summaries = [part.get("text", "") for block in blocks
                 if block.get("type") == "openai_item"
                 and block.get("item", {}).get("type") == "reasoning"
                 for part in block["item"].get("summary", [])]
    normalize = lambda value: "".join(value.split())
    return bool(text.strip() and summaries and
                normalize(text) == normalize("".join(summaries)))


def _remote_error(error):
    fields = error if isinstance(error, dict) else {}
    codes = {str(fields.get(key, '')).lower() for key in ('type', 'code')}
    permanent = {'authentication_error', 'permission_error', 'invalid_request_error',
                 'insufficient_quota', 'quota_exceeded', 'subscription_not_found',
                 'context_length_exceeded', 'billing_error'}
    temporary = {'upstream_error', 'server_error', 'stream_read_error',
                 'overloaded_error', 'temporarily_unavailable', 'rate_limit_error',
                 'rate_limit_exceeded', 'gateway_queue_full'}
    cls = RetryableProviderError if codes & temporary and not codes & permanent else ProviderError
    return cls(str(error))


def _url(base: str, path: str) -> str:
    base, path = base.rstrip("/"), path.strip("/")
    if base.endswith("$"):
        return base[:-1].rstrip("/")
    if base.endswith(path):
        return base
    return f"{base}/{path}" if re.search(r"/v\d+(/|$)", base) else f"{base}/v1/{path}"


def _claude_tools(tools):
    return [{
        "name": item["function"]["name"],
        "description": item["function"].get("description", ""),
        "input_schema": item["function"].get("parameters", {"type": "object", "properties": {}}),
    } for item in tools]


def _openai_tools(tools, responses_api):
    if not responses_api:
        return tools
    return [{"type": "function", **item["function"]} for item in tools]


class MonitorProviderClient:
    """Persistent provider history for one Monitor identity."""

    CONTROL_ACTIONS = {"wait", "intervene", "allow_complete"}

    def __init__(self, config_name: str, config: dict):
        self.config_name = config_name
        self.config = dict(config)
        self.api_key = self.config["apikey"]
        self.api_base = self.config["apibase"].rstrip("/")
        self.model = self.config.get("model", "")
        self.provider = self._provider_kind(config_name, self.config)
        self.api_mode = str(self.config.get("api_mode", "responses" if self.provider == "openai" else "messages"))
        self.max_tokens = int(self.config.get("max_tokens") or 8192)
        self.context_window = int(self.config.get("context_win") or 200000)
        self.history_char_limit = int(
            self.config.get("monitor_history_char_limit") or self.context_window * 3.5
        )
        self.history_target_chars = int(self.history_char_limit * 0.82)
        self.reasoning_effort = self.config.get("reasoning_effort")
        self.thinking_type = str(self.config.get("thinking_type") or "").lower()
        self.temperature = self.config.get("temperature", 1)
        self.connect_timeout = max(1, int(self.config.get("timeout", 10)))
        self.read_timeout = max(10, int(self.config.get("read_timeout", 300)))
        self.max_retries = max(0, int(self.config.get("max_retries", 2)))
        self.verify = self.config.get("verify", True)
        proxy = self.config.get("proxy")
        self.proxies = {"http": proxy, "https": proxy} if proxy else None
        self.system = ""
        self.history = []
        self.usage_records = []
        self.history_transforms = []
        self.request_attempts = []
        self._cancelled = threading.Event()
        self._active_lock = threading.Lock()
        self._active_response = None
        self.progress_callback = None

    def _progress(self, event, **fields):
        callback = getattr(self, 'progress_callback', None)
        if callback is not None:
            callback(event, **fields)

    @staticmethod
    def _provider_kind(name, config):
        explicit = str(config.get("provider", "")).lower()
        if explicit in {"anthropic", "claude"}: return "anthropic"
        if explicit in {"openai", "oai"}: return "openai"
        lowered = f"{name} {config.get('model', '')}".lower()
        return "anthropic" if "claude" in lowered else "openai"

    def cancel_active_response(self) -> bool:
        with self._active_lock:
            response = self._active_response
        if response is None:
            return False
        self._cancelled.set()
        try: response.close()
        except Exception: pass
        return True

    def history_measure(self) -> dict:
        encoded = json.dumps(self.history, ensure_ascii=False, default=str).encode("utf-8")
        return {
            "items": len(self.history), "characters": len(encoded),
            "sha256": hashlib.sha256(encoded).hexdigest(),
        }

    def export_history(self) -> list[dict]:
        return json.loads(json.dumps(self.history, ensure_ascii=False))

    def restore_history(self, history: list[dict]) -> None:
        self.history = json.loads(json.dumps(history, ensure_ascii=False))

    def record_tool_results(self, results: list[dict]) -> None:
        """Close tool calls in canonical history without starting another model turn."""
        if not results:
            return
        self.history.append({"role": "user", "content": [{
            "type": "tool_result",
            "tool_use_id": str(result.get("tool_use_id") or ""),
            "content": str(result.get("content") or ""),
        } for result in results]})

    @staticmethod
    def _bounded_block(value, limit=6000):
        if not isinstance(value, str) or len(value) <= limit:
            return value
        half = limit // 2
        return value[:half] + "\n[older tool output compacted]\n" + value[-half:]

    def _history_characters(self):
        return len(json.dumps(
            self.history, ensure_ascii=False, default=str
        ).encode("utf-8"))

    def _review_boundaries(self):
        """Return indexes after fully closed Monitor control-action reviews."""
        boundaries = []
        outstanding = set()
        control_calls = set()
        terminal_pending = False
        for index, message in enumerate(self.history):
            if message.get("role") == "assistant":
                for block in message.get("content") or []:
                    if block.get("type") != "tool_use":
                        continue
                    call_id = str(block.get("id") or "")
                    if call_id:
                        outstanding.add(call_id)
                    if block.get("name") in self.CONTROL_ACTIONS:
                        control_calls.add(call_id)
            elif message.get("role") == "user":
                for block in message.get("content") or []:
                    if block.get("type") == "tool_result":
                        call_id = str(block.get("tool_use_id") or "")
                        outstanding.discard(call_id)
                        if call_id in control_calls:
                            control_calls.discard(call_id)
                            try:
                                result = json.loads(block.get("content", ""))
                            except (ValueError, TypeError):
                                result = {}
                            # A phase handoff closes a tool exchange, not a review.
                            # Older archives lack the typed action; keep their
                            # acknowledged control-call boundary semantics.
                            if (isinstance(result, dict)
                                    and result.get("status") == "accepted"
                                    and result.get("control_action", "legacy")
                                    in self.CONTROL_ACTIONS | {"legacy"}):
                                terminal_pending = True
                if terminal_pending and not outstanding:
                    boundaries.append(index + 1)
                    terminal_pending = False
        return boundaries

    def _compact_old_tool_results(self, start, stop):
        for message in self.history[start:stop]:
            if message.get("role") != "user":
                continue
            for block in message.get("content") or []:
                if block.get("type") == "tool_result":
                    block["content"] = self._bounded_block(block.get("content", ""))

    def _exchange_boundaries(self):
        """Protocol-complete cuts, independent of whether a concern is resolved.

        Reuse the canonical tool-use/result pairing used by review boundaries.
        A parallel batch is indivisible, including signed reasoning in its
        assistant message. The current unfinished exchange is never retired.
        """
        boundaries, outstanding = [], set()
        for index, message in enumerate(self.history):
            blocks = message.get("content") or []
            if message.get("role") == "assistant":
                calls = [str(block.get("id") or "") for block in blocks
                         if block.get("type") == "tool_use"]
                outstanding.update(calls)
                if not calls and not outstanding:
                    boundaries.append(index + 1)
            elif message.get("role") == "user":
                results = [block for block in blocks if block.get("type") == "tool_result"]
                for block in results:
                    outstanding.discard(str(block.get("tool_use_id") or ""))
                if results and not outstanding:
                    boundaries.append(index + 1)
        return boundaries

    def _compact_history(self):
        before = self.history_measure()
        if before["characters"] <= self.history_char_limit:
            return
        if getattr(self, "prepare_continuation", None) is not None:
            try:
                self._relieve_tool_result_pressure()
                before = self.history_measure()
                if before["characters"] <= self.history_target_chars:
                    return
                self._compact_with_continuation(before)
            except ProviderRecoveryExhausted:
                raise
            except Exception as exc:
                # Evidence remains in history/archives. Retrying via a new wake
                # would only append more input; expose a terminal monitor fault.
                raise HistoryCapacityError(
                    "Monitor continuation failed; history preserved: " + type(exc).__name__
                ) from exc
            if self.history_measure()["characters"] > self.history_char_limit:
                raise HistoryCapacityError(
                    "Monitor history remains over capacity after lossless evidence archival; "
                    "retained dialogue cannot be retired safely. History preserved."
                )
            return
        continuation = None
        prepare = getattr(self, "prepare_continuation", None)
        if prepare is not None:
            # Save semantic continuity before destructive trimming. Failure leaves history intact.
            continuation = prepare()

        # Review boundaries are defined by acknowledged control actions, not by
        # a fixed number of messages. Never split a tool call from its result.
        boundaries = self._review_boundaries()
        head_end = boundaries[0] if boundaries else 0
        recent_floor = max(head_end, len(self.history) - 16)
        old_end = max((value for value in boundaries if value <= recent_floor), default=head_end)
        self._compact_old_tool_results(head_end, old_end)
        removed = 0
        while self._history_characters() > self.history_target_chars:
            boundaries = self._review_boundaries()
            if not boundaries:
                break
            head_end = boundaries[0]
            removable = [
                value for value in boundaries[1:]
                if len(self.history) - value >= 16
            ]
            if not removable:
                break
            end = removable[0]
            del self.history[head_end:end]
            removed += end - head_end

        # An unusually large recent inspection result can itself exceed the
        # budget. Bound tool outputs outside the latest request without
        # rewriting signed thinking or provider reasoning items.
        if self._history_characters() > self.history_char_limit:
            boundaries = self._review_boundaries()
            head_end = boundaries[0] if boundaries else 0
            for message in self.history[head_end:-2]:
                if message.get("role") != "user":
                    continue
                for block in message.get("content") or []:
                    if block.get("type") == "tool_result":
                        block["content"] = self._bounded_block(block.get("content", ""), 12000)

        if continuation:
            boundaries = self._review_boundaries()
            position = boundaries[0] if boundaries else 0
            self.history.insert(position, {"role": "user", "content": [{
                "type": "text", "text": "Your working understanding carried forward before history compaction:\n" + continuation,
            }]})
        after = self.history_measure()
        self.history_transforms.append({
            "kind": "monitor_history_compaction",
            "before": before,
            "after": after,
            "removed_messages": removed,
            "char_limit": self.history_char_limit,
            "target_chars": self.history_target_chars,
        })

    def _relieve_tool_result_pressure(self):
        """Move oversized payloads, not decisions, to exact retrievable storage."""
        before = self.history_measure()
        archive = getattr(self, "archive_continuation_history", None)
        if archive is None:
            raise ProviderError("Semantic compaction requires a retrievable history archive")
        candidates = []
        for mi, message in enumerate(self.history):
            for bi, block in enumerate(message.get("content") or []):
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                value = block.get("content")
                if isinstance(value, str) and len(value.encode("utf-8")) > 12000:
                    candidates.append((mi, bi))
        if not candidates:
            return
        location = archive(self.export_history())
        changed = 0
        for mi, bi in candidates:
            if self.history_measure()["characters"] <= self.history_target_chars:
                break
            block = self.history[mi]["content"][bi]
            value = block["content"]
            block["content"] = (
                "Large tool result: only beginning/end excerpts are in this context, not the full evidence. "
                "Use file_read/code_run to inspect the full JSON string at " + location
                + f", JSON location [{mi}].content[{bi}].content (zero-based). "
                "The omitted middle may contain relevant evidence; excerpts alone cannot establish absence.\n"
                + value[:2000] + "\n[Middle archived, not shown]\n" + value[-2000:]
            )
            changed += 1
        self.history_transforms.append({
            "kind": "monitor_tool_payload_archival", "before": before,
            "after": self.history_measure(), "archive": location, "results_archived": changed,
        })

    def _compact_with_continuation(self, before):
        """Retire a protocol-complete prefix, after planning and durable archival.

        Retain recent exchanges, not arbitrarily long review lifetimes. The
        same-model continuation carries unresolved concerns across this cut.
        """
        boundaries = self._exchange_boundaries()
        # Keep at least the latest exchange plus any pending one. Reserve room
        # for the handoff; do not require a semantic issue to close to compact.
        candidates = [cut for cut in boundaries[:-1] if cut < len(self.history)]
        if not candidates:
            # No safe prefix can be retired. Do not repeatedly ask for a note
            # while leaving exactly the same oversized conversation in place.
            self._progress("compaction_deferred", reason="no_retirable_exchange_prefix",
                           history_characters=before["characters"])
            return
        cut = candidates[-1]
        for candidate in candidates:
            tail = self.history[candidate:]
            size = len(json.dumps(tail, ensure_ascii=False).encode("utf-8"))
            if size <= self.history_target_chars * 0.75:
                cut = candidate
                break
        archive = getattr(self, "archive_continuation_history", None)
        if archive is None:
            raise ProviderError("Semantic compaction requires a retrievable history archive")
        # Archive first: no evidence is silently discarded if maintenance fails.
        location = archive(self.export_history())
        previous_context = getattr(self, "continuation_context", None)
        self.continuation_context = {"archive": location, "retired_messages": cut}
        try:
            note = self.prepare_continuation()
        finally:
            self.continuation_context = previous_context
        carried = {
            "role": "user", "content": [{"type": "text", "text":
                "Current working understanding, written after reviewing the retained dialogue below. "
                "It is revisable, not a new task instruction. Full pre-compaction history: "
                + location + "\n" + note}],
        }
        # A previous carried note is in the retired prefix, not duplicated.
        replacement = [carried] + self.history[cut:]
        replacement_size = len(json.dumps(replacement, ensure_ascii=False).encode("utf-8"))
        if replacement_size > self.history_char_limit:
            raise HistoryCapacityError(
                "Monitor handoff and latest exchange exceed capacity; original history preserved."
            )
        self.history = replacement
        self._progress('compaction_committed',
                       transaction_id=getattr(self, 'continuation_transaction_id', None),
                       removed_messages=cut, archive=location)
        after = self.history_measure()
        self.history_transforms.append({
            "kind": "monitor_history_compaction", "before": before, "after": after,
            "removed_messages": cut, "char_limit": self.history_char_limit,
            "target_chars": self.history_target_chars, "archive": location,
            "target_reached": after["characters"] <= self.history_target_chars,
            "boundary_kind": "protocol_exchange", "size_unit": "utf8_bytes",
        })

    def drain_telemetry(self):
        value = {
            "usage": list(self.usage_records),
            "history_transforms": list(self.history_transforms),
        }
        if self.request_attempts:
            value['request_attempts'] = list(self.request_attempts)
        self.request_attempts.clear()
        self.usage_records.clear()
        self.history_transforms.clear()
        return value

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        user_blocks = []
        for message in messages:
            if message["role"] == "system":
                self.system = str(message.get("content") or "")
                continue
            for result in message.get("tool_results") or []:
                user_blocks.append({
                    "type": "tool_result", "tool_use_id": result.get("tool_use_id", ""),
                    "content": result.get("content", ""),
                })
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                user_blocks.append({"type": "text", "text": content})
        if not user_blocks:
            user_blocks = [{"type": "text", "text": "."}]
        self.history.append({"role": "user", "content": user_blocks})
        self._compact_history()
        blocks, usage = self._request(tools)
        if blocks:
            self.history.append({"role": "assistant", "content": blocks})
        text = "\n".join(block.get("text", "") for block in blocks if block.get("type") == "text")
        calls = [ToolCall(
            str(block.get("id") or uuid.uuid4().hex), str(block.get("name") or ""),
            json.dumps(block.get("input") or {}, ensure_ascii=False),
        ) for block in blocks if block.get("type") == "tool_use"]
        self.usage_records.append(dict(usage))
        return ModelResponse(text, calls, usage)

    def _request(self, tools):
        # Request-local context never becomes another permanent history copy.
        # Read after compaction, so a newly written handoff is visible immediately.
        prepare = getattr(self, 'prepare_active_context', None)
        context = prepare() if tools and prepare is not None else None
        entry = {"role": "user", "content": [{"type": "text", "text": context}]} if context else None
        if entry is not None:
            self.history.append(entry)
        try:
            return self._request_with_recovery(tools)
        finally:
            if entry is not None:
                assert self.history[-1] is entry
                self.history.pop()

    def _request_with_recovery(self, tools):
        # Runtime-owned recovery stays inside this request: no new wake, tool
        # replay, history append, or synthetic completion decision.
        deadline = getattr(self, 'recovery_deadline', None)
        if deadline is None:
            return self._request_batch(tools)
        stop = self.recovery_stop
        for batch in range(2):
            if stop.is_set() or time.monotonic() >= deadline:
                raise ProviderRecoveryExhausted('Monitor stopped or task budget exhausted')
            try:
                return self._request_batch(tools)
            except RetryableProviderError as exc:
                if batch == 1:
                    raise ProviderRecoveryExhausted(str(exc)) from exc
                delay = min(30.0, max(0.0, deadline - time.monotonic()))
                self._progress('transport_recovery_wait', seconds=delay,
                               next_batch=2, error_type=type(exc).__name__)
                if stop.wait(delay) or time.monotonic() >= deadline:
                    raise ProviderRecoveryExhausted('Monitor stopped or task budget exhausted') from exc

    def _request_batch(self, tools):
        last_error = None
        self._cancelled.clear()
        for attempt in range(self.max_retries + 1):
            deadline = getattr(self, 'recovery_deadline', None)
            if deadline is not None and (self.recovery_stop.is_set() or time.monotonic() >= deadline):
                raise ProviderRecoveryExhausted('Monitor stopped or task budget exhausted')
            started = time.monotonic()
            request_id = uuid.uuid4().hex
            self._progress_request_id = request_id
            self.last_response_metadata = {}
            record = {'attempt': attempt + 1, 'started_at': time.time(),
                      'history_characters': self.history_measure()['characters'],
                      'purpose': getattr(self, 'request_purpose', 'review'),
                      'transaction_id': (getattr(self, 'continuation_transaction_id', None)
                                         if getattr(self, 'request_purpose', 'review') in ('continuation', 'format_repair')
                                         else None)}
            self._progress('request_started', request_id=request_id, **record)
            try:
                result = self._request_once(tools)
                self._progress('response_metadata', request_id=request_id,
                               metadata=getattr(self, 'last_response_metadata', {}))
                if self._cancelled.is_set():
                    raise ProviderError('Provider request cancelled')
                self._progress('request_usage', request_id=request_id, usage=result[1])
                # Completed transport is not necessarily a usable agent response.
                # Retry before committing history or consuming a review turn.
                if record['purpose'] not in ('continuation', 'format_repair') and not any(
                    (block.get('type') == 'text' and str(block.get('text') or '').strip())
                    or (block.get('type') == 'tool_use' and str(block.get('name') or '').strip())
                    for block in result[0]
                ):
                    self._progress('response_empty', request_id=request_id)
                    raise RetryableProviderError('Empty model response: no text or tool call')
                record['outcome'] = 'success'
                return result
            except (RetryableProviderError, requests.Timeout, requests.ConnectionError,
                    requests.exceptions.ChunkedEncodingError) as exc:
                last_error = exc
                record.update(outcome='retryable_error', error_type=type(exc).__name__,
                             error_chain=failure_chain(exc))
                if self._cancelled.is_set():
                    raise ProviderError('Provider request cancelled') from exc
                if attempt >= self.max_retries:
                    record['outcome'] = 'retries_exhausted'
                    break
                delay = min(8, 1.5 * (2 ** attempt))
                record['retry_delay_seconds'] = delay
                self._progress('request_retry_wait', request_id=request_id, seconds=delay,
                               error_type=type(exc).__name__)
                if self._cancelled.wait(delay):
                    raise ProviderError('Provider request cancelled') from exc
            except Exception as exc:
                record.update(outcome='error', error_type=type(exc).__name__,
                             error_chain=failure_chain(exc))
                raise
            finally:
                if self._cancelled.is_set(): record['outcome'] = 'cancelled'
                record['duration_seconds'] = time.monotonic() - started
                self.request_attempts.append(record)
                self._progress('request_finished', request_id=request_id, **record)
        raise RetryableProviderError(f"Provider request failed: {last_error}") from last_error

    def _request_once(self, tools):
        if self.provider == "anthropic":
            url, headers, payload = self._anthropic_request(tools)
            parser = self._parse_anthropic
        else:
            url, headers, payload = self._openai_request(tools)
            parser = self._parse_openai_responses if self.api_mode.startswith("response") else self._parse_openai_chat
        if self.config.get('transport_route'):
            headers['x-model-route'] = self.config['transport_route']
        with requests.post(
            url, headers=headers, json=payload, stream=True,
            timeout=(self.connect_timeout, self.read_timeout), proxies=self.proxies, verify=self.verify,
        ) as response:
            self._progress('response_headers', request_id=self._progress_request_id,
                           status_code=response.status_code)
            with self._active_lock: self._active_response = response
            try:
                if response.status_code >= 400:
                    try: body = response.text[:500]
                    except Exception: body = ""
                    if response.status_code in {408, 429, 500, 502, 503, 504}:
                        try: error = response.json().get('error', {})
                        except (ValueError, AttributeError): error = {}
                        classified = _remote_error(error)
                        # Explicit permanent errors override a transient HTTP status.
                        if error and not isinstance(classified, RetryableProviderError):
                            raise classified
                        raise RetryableProviderError(f"HTTP {response.status_code}: {body}")
                    raise ProviderError(f"HTTP {response.status_code}: {body}")
                return parser(self._progress_lines(response.iter_lines()))
            finally:
                with self._active_lock:
                    if self._active_response is response: self._active_response = None

    def _progress_lines(self, lines):
        last = 0.0
        count = 0
        size = 0
        for line in lines:
            count += 1
            size += len(line)
            now = time.monotonic()
            if count == 1 or now - last >= 5:
                self._progress('stream_activity', request_id=self._progress_request_id,
                               lines=count, bytes_or_characters=size)
                last = now
            yield line

    def _anthropic_request(self, tools):
        headers = {
            "Content-Type": "application/json", "anthropic-version": "2023-06-01",
            "Accept": "application/json", "user-agent": "longcontext-monitor/1.0",
        }
        if self.api_key.startswith("sk-ant-"): headers["x-api-key"] = self.api_key
        else: headers["authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model, "messages": self.history, "max_tokens": self.max_tokens,
            "stream": True, "system": self.system, "tools": _claude_tools(tools),
        }
        headers["anthropic-beta"] = ",".join([
            "interleaved-thinking-2025-05-14", "redact-thinking-2026-02-12",
            "context-management-2025-06-27", "effort-2025-11-24",
        ])
        if self.temperature != 1: payload["temperature"] = self.temperature
        if self.thinking_type == "adaptive" or self.reasoning_effort:
            payload["thinking"] = {"type": "adaptive"}
        if self.reasoning_effort:
            payload["output_config"] = {"effort": self.reasoning_effort}
        return _url(self.api_base, "messages") + "?beta=true", headers, payload

    def _openai_request(self, tools):
        headers = {
            "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
            "Accept": "text/event-stream", "User-Agent": "longcontext-monitor/1.0",
        }
        if self.api_mode.startswith("response"):
            payload = {
                "model": self.model, "input": self._responses_history(), "stream": True,
                "instructions": self.system, "tools": _openai_tools(tools, True),
                "include": ["reasoning.encrypted_content"],
            }
            if self.max_tokens: payload["max_output_tokens"] = self.max_tokens
            if self.reasoning_effort: payload["reasoning"] = {"effort": self.reasoning_effort}
            return _url(self.api_base, "responses"), headers, payload
        messages = [{"role": "system", "content": self.system}] + self._chat_history()
        payload = {"model": self.model, "messages": messages, "stream": True,
                   "stream_options": {"include_usage": True}, "tools": _openai_tools(tools, False)}
        if self.max_tokens: payload["max_completion_tokens"] = self.max_tokens
        if self.reasoning_effort: payload["reasoning_effort"] = self.reasoning_effort
        if self.temperature != 1: payload["temperature"] = self.temperature
        return _url(self.api_base, "chat/completions"), headers, payload

    def _chat_history(self):
        result = []
        for message in self.history:
            if message["role"] == "assistant":
                text = "\n".join(x.get("text", "") for x in message["content"] if x.get("type") == "text")
                calls = [{"id": x["id"], "type": "function", "function": {
                    "name": x["name"], "arguments": json.dumps(x.get("input") or {})
                }} for x in message["content"] if x.get("type") == "tool_use"]
                result.append({"role": "assistant", "content": text or None, "tool_calls": calls})
            else:
                texts = [x.get("text", "") for x in message["content"] if x.get("type") == "text"]
                if texts: result.append({"role": "user", "content": "\n".join(texts)})
                for block in message["content"]:
                    if block.get("type") == "tool_result":
                        result.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block.get("content", "")})
        return result

    def _responses_history(self):
        result = []
        for message in self.history:
            if message["role"] == "assistant":
                text = "\n".join(x.get("text", "") for x in message["content"] if x.get("type") == "text")
                if text: result.append({"role": "assistant", "content": text})
                for block in message["content"]:
                    if block.get("type") == "openai_item":
                        item = dict(block["item"])
                        # Relay may return reasoning.status but reject it on
                        # input. Normalize only wire metadata; keep the archived
                        # item and all reasoning/context contents unchanged.
                        if item.get("type") == "reasoning":
                            item.pop("status", None)
                        result.append(item)
                    elif block.get("type") == "tool_use": result.append({
                        "type": "function_call", "call_id": block["id"], "name": block["name"],
                        "arguments": json.dumps(block.get("input") or {}),
                    })
            else:
                texts = [x.get("text", "") for x in message["content"] if x.get("type") == "text"]
                if texts: result.append({"role": "user", "content": "\n".join(texts)})
                for block in message["content"]:
                    if block.get("type") == "tool_result": result.append({
                        "type": "function_call_output", "call_id": block["tool_use_id"],
                        "output": block.get("content", ""),
                    })
        return result

    @staticmethod
    def _events(lines):
        for line in lines:
            if not line: continue
            text = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
            if not text.startswith("data:"): continue
            data = text[5:].strip()
            if data == "[DONE]": return
            try: yield json.loads(data)
            except json.JSONDecodeError: continue

    def _parse_anthropic(self, lines):
        blocks, current, tool_json, usage = [], None, "", {}
        metadata = {'provider': 'anthropic', 'stream_complete': False,
                    'stop_reason': None, 'provider_message_id': None}
        self.last_response_metadata = metadata
        completed = False
        for event in self._events(lines):
            kind = event.get("type")
            if kind == "message_start":
                usage.update(event.get("message", {}).get("usage", {}) or {})
                metadata['provider_message_id'] = event.get('message', {}).get('id')
            elif kind == "content_block_start":
                block = event.get("content_block", {})
                current = None
                if block.get("type") == "text": current = {"type": "text", "text": ""}
                elif block.get("type") == "thinking": current = {"type": "thinking", "thinking": "", "signature": ""}
                elif block.get("type") == "redacted_thinking": current = dict(block)
                elif block.get("type") == "tool_use":
                    current = {"type": "tool_use", "id": block.get("id", ""), "name": block.get("name", ""), "input": {}}
                    tool_json = ""
            elif kind == "content_block_delta" and current:
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta": current["text"] += delta.get("text", "")
                elif delta.get("type") == "thinking_delta": current["thinking"] += delta.get("thinking", "")
                elif delta.get("type") == "signature_delta": current["signature"] += delta.get("signature", "")
                elif delta.get("type") == "input_json_delta": tool_json += delta.get("partial_json", "")
            elif kind == "content_block_stop" and current:
                if current["type"] == "tool_use":
                    try: current["input"] = json.loads(tool_json or "{}")
                    except json.JSONDecodeError: current["input"] = {"_raw": tool_json}
                blocks.append(current); current = None
            elif kind == "message_delta":
                usage.update(event.get("usage", {}) or {})
                if 'stop_reason' in event.get('delta', {}):
                    metadata['stop_reason'] = event['delta']['stop_reason']
            elif kind == "error": raise _remote_error(event.get("error"))
            elif kind == "message_stop":
                completed = True
                break
        if not completed or current is not None:
            raise RetryableProviderError('Anthropic stream ended before a complete message_stop')
        metadata.update(stream_complete=True, response_block_types=[b['type'] for b in blocks])
        return blocks, usage

    def _parse_openai_responses(self, lines):
        text, usage, provider_items = "", {}, {}
        tool_snapshots, argument_deltas = {}, {}
        messages = {}
        final_output = None
        completed = False
        for event in self._events(lines):
            kind = event.get("type")
            if kind == "response.output_text.delta": text += event.get("delta", "")
            elif kind == "response.output_item.added":
                item = event.get("item", {})
                if item.get("type") == "function_call":
                    index = event.get("output_index", 0)
                    tool_snapshots.setdefault(index, []).append(('added', dict(item)))
                elif item.get("type") == "reasoning":
                    provider_items[event.get("output_index", 0)] = dict(item)
            elif kind == "response.output_item.done":
                item = event.get("item", {})
                if item.get("type") == "reasoning":
                    provider_items[event.get("output_index", 0)] = dict(item)
                elif item.get("type") == "message":
                    messages[event.get("output_index", 0)] = dict(item)
                elif item.get("type") == "function_call":
                    tool_snapshots.setdefault(event.get('output_index', 0), []).append(('item_done', dict(item)))
            elif kind == "response.function_call_arguments.delta":
                index = event.get("output_index", 0)
                argument_deltas[index] = argument_deltas.get(index, '') + event.get('delta', '')
            elif kind == "response.function_call_arguments.done":
                index = event.get("output_index", 0)
                tool_snapshots.setdefault(index, []).append(('arguments_done', dict(event)))
            elif kind == "response.completed":
                completed = True
                usage = event.get("response", {}).get("usage", {}) or {}
                output = event.get("response", {}).get("output")
                if isinstance(output, list):
                    final_output = output
                    for index, item in enumerate(output):
                        if item.get("type") == "reasoning":
                            provider_items[index] = dict(item)
                self._progress('response_completed',
                               request_id=getattr(self, '_progress_request_id', None))
                break
            elif kind == "error": raise _remote_error(event.get("error"))
            elif kind == "response.failed":
                raise _remote_error((event.get('response') or {}).get('error'))
            elif kind == "response.incomplete":
                details = (event.get('response') or {}).get('incomplete_details') or {}
                self._progress('response_incomplete', reason=details.get('reason'),
                               request_id=getattr(self, '_progress_request_id', None))
                # A declared output limit is not fixed by blindly repeating the
                # same request. Never execute partially generated tool arguments.
                raise ProviderError(f"Monitor response explicitly incomplete: {details}")
        if not completed:
            self._progress('response_truncated',
                           request_id=getattr(self, '_progress_request_id', None))
            raise RetryableProviderError("Responses stream ended without response.completed")
        blocks = [{"type": "openai_item", "item": provider_items[index]} for index in sorted(provider_items)]
        final_items = final_output if final_output is not None else [messages[i] for i in sorted(messages)]
        has_final = final_output is not None or bool(messages)
        final_text = "".join(part.get("text", "") for item in final_items
                             if item.get("type") == "message" and item.get("role", "assistant") == "assistant"
                             for part in item.get("content", []) if part.get("type") == "output_text")
        # Final message bodies can recover a missing/truncated delta stream.
        # Contradictory bodies are not silently merged or promoted to memory.
        # A relay may emit whitespace before a tool-only final response. It has
        # no semantic body to preserve; the tools still pass the checks below.
        tool_only_padding = (final_output is not None and bool(text) and text.isspace()
                             and any(item.get('type') == 'function_call' for item in final_items)
                             and all(item.get('type') in ('function_call', 'reasoning') for item in final_items))
        mismatch = has_final and bool(text) and not final_text.startswith(text) and not tool_only_padding
        selected = final_text if has_final else text
        echo = is_reasoning_echo(selected, blocks)
        self._progress("response_text_contract", request_id=getattr(self, "_progress_request_id", None),
                       source="completed_output" if final_output is not None else "item_done" if messages else "delta",
                       delta_characters=len(text), final_characters=len(final_text),
                       ignored_tool_only_whitespace=tool_only_padding,
                       delta_codepoints=[ord(c) for c in text] if len(text) <= 8 else None,
                       reasoning_echo=echo, mismatch=mismatch,
                       final_item_types=[item.get("type") for item in final_items],
                       usage={key: usage[key] for key in ("input_tokens", "output_tokens", "total_tokens")
                              if key in usage})
        if mismatch or echo:
            raise RetryableProviderError("Response body conflicts with final output or duplicates reasoning summary")
        text = selected
        if text: blocks.append({"type": "text", "text": text})
        final_calls = ({i: item for i, item in enumerate(final_output)
                        if item.get('type') == 'function_call'} if final_output is not None else None)
        indices = set(tool_snapshots) | set(argument_deltas) | set(final_calls or {})
        for index in sorted(indices):
            snapshots = list(tool_snapshots.get(index, []))
            if final_calls is not None and index in final_calls:
                snapshots.append(('completed', final_calls[index]))
            try:
                if final_calls is not None and index not in final_calls:
                    raise ValueError('streamed call absent from final output')
                identities = {'call_id': set(), 'name': set(), 'item_id': set()}
                full_arguments = []
                for source, item in snapshots:
                    for field in identities:
                        # Some relays repackage final output items. call_id links
                        # tool results; the final object's id is not that link.
                        # Still require identity consistency within the stream.
                        if field == 'item_id' and source == 'completed':
                            continue
                        value = item.get('id' if field == 'item_id' and source != 'arguments_done' else field)
                        if value:
                            identities[field].add(value)
                    raw = item.get('arguments')
                    if raw is not None and (source != 'added' or raw):
                        parsed = json.loads(raw)
                        if not isinstance(parsed, dict):
                            raise ValueError('arguments must be an object')
                        full_arguments.append((raw, parsed))
                if any(len(values) > 1 for values in identities.values()):
                    raise ValueError('tool identity changed across events')
                delta = argument_deltas.get(index, '')
                if full_arguments:
                    raw, arguments = full_arguments[-1]
                    if any(value != arguments for _, value in full_arguments):
                        raise ValueError('final argument objects disagree')
                    if delta:
                        try:
                            delta_matches = json.loads(delta) == arguments
                        except json.JSONDecodeError:
                            delta_matches = raw.startswith(delta)
                        if not delta_matches:
                            raise ValueError('argument delta contradicts final arguments')
                else:
                    arguments = json.loads(delta or '{}')
                if not isinstance(arguments, dict):
                    raise ValueError('arguments must be an object')
                if not identities['call_id'] or not identities['name']:
                    raise ValueError('missing callable identity')
            except (ValueError, TypeError) as exc:
                self._progress('response_tool_contract', output_index=index, mismatch=True,
                               sources=[source for source, _ in snapshots], reason=str(exc),
                               request_id=getattr(self, '_progress_request_id', None))
                raise RetryableProviderError('Tool stream contract mismatch: ' + str(exc)) from exc
            self._progress('response_tool_contract', output_index=index, mismatch=False,
                           sources=[source for source, _ in snapshots],
                           final_item_id_rewritten=bool(final_calls and index in final_calls
                               and identities['item_id'] and final_calls[index].get('id')
                               and final_calls[index]['id'] not in identities['item_id']),
                           arguments_sha256=hashlib.sha256(json.dumps(arguments, sort_keys=True,
                               ensure_ascii=False).encode('utf-8')).hexdigest(),
                           request_id=getattr(self, '_progress_request_id', None))
            blocks.append({'type': 'tool_use', 'id': next(iter(identities['call_id'])),
                           'name': next(iter(identities['name'])), 'input': arguments})
        return blocks, usage

    def _parse_openai_chat(self, lines):
        text, calls, usage = "", {}, {}
        for event in self._events(lines):
            usage.update(event.get("usage") or {})
            choice = (event.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            text += delta.get("content") or ""
            for item in delta.get("tool_calls") or []:
                index = item.get("index", 0)
                call = calls.setdefault(index, {"id": "", "name": "", "args": ""})
                call["id"] = item.get("id") or call["id"]
                function = item.get("function") or {}
                call["name"] += function.get("name") or ""
                call["args"] += function.get("arguments") or ""
        blocks = [{"type": "text", "text": text}] if text else []
        for index in sorted(calls):
            call = calls[index]
            try: inputs = json.loads(call["args"] or "{}")
            except json.JSONDecodeError: inputs = {"_raw": call["args"]}
            blocks.append({"type": "tool_use", "id": call["id"], "name": call["name"], "input": inputs})
        return blocks, usage
