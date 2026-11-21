"""Opt-in, host-only capture of actual provider response bytes.

This module does not issue requests, read authentication headers, or alter a
response. All failures are best-effort audit failures, not model failures.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

import httpx


ENABLE_ENV = "PMA_PROVIDER_RESPONSE_CAPTURE"
ROOT_ENV = "PMA_PROVIDER_RESPONSE_CAPTURE_ROOT"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_line(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _response_id(body: bytes) -> str | None:
    """Read an ID only from captured bytes; do not invent one from a request."""
    try:
        value = json.loads(body)
        if isinstance(value, dict) and isinstance(value.get("id"), str):
            return value["id"]
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    for line in body.splitlines():
        if not line.startswith(b"data:"):
            continue
        try:
            value = json.loads(line[5:].strip())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            message = value.get("message")
            if isinstance(message, dict) and isinstance(message.get("id"), str):
                return message["id"]
            if isinstance(value.get("id"), str):
                return value["id"]
    return None


def _stream_events(body: bytes) -> list[bytes]:
    """Split captured SSE bytes after consumption, retaining exact event bytes."""
    events = []
    start = 0
    for match in re.finditer(rb"\r?\n\r?\n", body):
        events.append(body[start:match.end()])
        start = match.end()
    if start < len(body):
        events.append(body[start:])
    return events


def _reasoning_kind(value: dict, *, stream: bool) -> str:
    """Inspect Anthropic Messages response positions, never arbitrary tool input."""
    kinds = set()

    def block(item):
        if not isinstance(item, dict):
            return
        if item.get("type") == "redacted_thinking":
            kinds.add("unreadable_block")
        elif item.get("type") == "thinking":
            content = item.get("thinking")
            if isinstance(content, str) and content:
                kinds.add("readable_text")
            elif content == "" and item.get("signature"):
                kinds.add("empty_text_signed")
            elif content is None and "thinking" in item:
                kinds.add("explicit_null")

    if stream:
        event = value.get("type")
        if event == "message_start":
            for item in (value.get("message") or {}).get("content") or []:
                block(item)
        elif event == "content_block_start":
            block(value.get("content_block"))
        elif event == "content_block_delta":
            delta = value.get("delta") or {}
            if delta.get("type") == "thinking_delta":
                content = delta.get("thinking")
                if isinstance(content, str) and content:
                    kinds.add("readable_text")
                elif content is None and "thinking" in delta:
                    kinds.add("explicit_null")
            elif delta.get("type") == "signature_delta" and delta.get("signature"):
                kinds.add("empty_text_signed")
    else:
        for item in value.get("content") or []:
            block(item)
        for key in ("thinking", "reasoning_content"):
            if key in value:
                content = value[key]
                if isinstance(content, str) and content:
                    kinds.add("readable_text")
                elif content is None:
                    kinds.add("explicit_null")
    for kind in ("readable_text", "empty_text_signed", "unreadable_block",
                 "explicit_null"):
        if kind in kinds:
            return kind
    return "not_returned"


def _buffered_kind(body: bytes) -> str:
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "unknown"
    return _reasoning_kind(value, stream=False) if isinstance(value, dict) else "unknown"


def _stream_result(body: bytes, *, consumed_to_eof: bool) -> tuple[str, str]:
    """Require protocol message_stop; EOF and HTTP 200 alone are insufficient."""
    if not consumed_to_eof:
        return "interrupted", "unknown"
    kinds = []
    stopped = False
    errored = False
    events = _stream_events(body)
    trailing_partial = bool(events and not events[-1].endswith((b"\n\n", b"\r\n\r\n")))
    try:
        for event in events:
            if not event.endswith((b"\n\n", b"\r\n\r\n")):
                continue
            event_name = None
            data_lines = []
            for line in event.splitlines():
                if line.startswith(b"event:"):
                    event_name = line[6:].strip().decode("utf-8")
                elif line.startswith(b"data:"):
                    data_lines.append(line[5:].strip())
            if event_name == "error":
                errored = True
            if not data_lines:
                continue
            raw = b"\n".join(data_lines)
            if raw == b"[DONE]":
                continue
            value = json.loads(raw)
            if not isinstance(value, dict):
                return "interrupted", "unknown"
            if value.get("type") == "error":
                errored = True
            if value.get("type") == "message_stop" or event_name == "message_stop":
                stopped = True
            kinds.append(_reasoning_kind(value, stream=True))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "interrupted", "unknown"
    if errored:
        return "stream_error", "unknown"
    if trailing_partial or not stopped:
        return "interrupted", "unknown"
    for kind in ("readable_text", "empty_text_signed", "unreadable_block",
                 "explicit_null"):
        if kind in kinds:
            return "normal_termination", kind
    return "normal_termination", "not_returned"


class ResponseSidecar:
    def __init__(self, root: Path, run_id: str, status_path: Path):
        if not run_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in run_id):
            raise ValueError("invalid run id for provider capture")
        self.root = root / run_id
        self.root.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.status_path = status_path

    @classmethod
    def from_environment(cls, environ: dict, *, run_id: str, private: Path,
                         requests: Path, responses: Path):
        if environ.get(ENABLE_ENV) != "1":
            return None
        # Keep capture metadata outside the ordinary archive projection too.
        status = private / "provider_capture_status.jsonl"
        try:
            text = environ.get(ROOT_ENV, "")
            root = Path(text)
            if not text or not root.is_absolute():
                raise ValueError("capture root must be an absolute local path")
            root = root.resolve(strict=False)
            run_root = private.parent.resolve(strict=False)
            if (root == run_root or root.is_relative_to(run_root)
                    or root == requests.parent or root.is_relative_to(requests.parent)
                    or root == responses.parent or root.is_relative_to(responses.parent)):
                raise ValueError("capture root must be outside run and shared spool")
            return cls(root, run_id, status)
        except Exception as exc:
            cls._safe_status(status, {"run_id": run_id, "capture_status": "unavailable",
                                      "error_type": type(exc).__name__})
            return None

    @staticmethod
    def _safe_status(path: Path, value: dict) -> None:
        try:
            _write_line(path, value)
        except Exception as exc:
            # This fallback is metadata only. Capture failure must not change
            # provider requests, retries, tool receipts or Task execution.
            print(f"provider response capture status write failed: {type(exc).__name__}",
                  file=sys.stderr)

    def _status(self, value: dict) -> None:
        self._safe_status(self.status_path, value)

    def _base(self, metadata: dict) -> Path:
        return self.root / (f"request-{metadata['request_index']:06d}"
                            f"-call-{metadata['call_sequence'] or 0:06d}"
                            f"-attempt-{metadata['attempt_in_call']:03d}")

    def capture(self, response: httpx.Response, metadata: dict, *, stream: bool) -> None:
        """Observe buffered bytes or wrap an unconsumed stream without reading it."""
        base = self._base(metadata)
        safe = {key: metadata.get(key) for key in (
            "run_id", "wake", "call_sequence", "request_index", "attempt_in_call",
            "route_kind", "model", "thinking_present", "thinking", "output_config_present",
            "output_config", "reasoning_effort_present", "reasoning_effort",
            "temperature_present", "temperature", "http_status")}
        safe["captured_epoch"] = time.time()
        if stream:
            try:
                writer = _StreamCapture(base, safe, self)
                response.stream = _TeeAsyncStream(response.stream, writer)
            except Exception as exc:
                self._status({**safe, "capture_status": "failed",
                              "error_type": type(exc).__name__})
            return
        try:
            body = response.content  # Already buffered by httpx.send(stream=False).
            path = base.with_suffix(".response.bin")
            with path.open("xb") as file:
                file.write(body)
                file.flush()
                os.fsync(file.fileno())
            self._status({**safe, "capture_status": "complete", "mode": "buffered",
                          "body_path": str(path), "body_bytes": len(body),
                          "body_sha256": _sha(body), "response_id": _response_id(body),
                          "reasoning_record_kind": _buffered_kind(body)})
        except Exception as exc:
            self._status({**safe, "capture_status": "failed", "mode": "buffered",
                          "error_type": type(exc).__name__})


class _StreamCapture:
    def __init__(self, base: Path, metadata: dict, sidecar: ResponseSidecar):
        self.base = base
        self.metadata = metadata
        self.sidecar = sidecar
        self.path = base.with_suffix(".stream.bin")
        self.file = self.path.open("xb")
        self.offset = 0
        self.chunks = []
        self.failed = False
        self.finished = False

    def write(self, chunk: bytes) -> None:
        if self.failed:
            return
        try:
            self.file.write(chunk)
            self.chunks.append({"ordinal": len(self.chunks) + 1, "offset": self.offset,
                                "bytes": len(chunk), "sha256": _sha(chunk)})
            self.offset += len(chunk)
        except Exception as exc:
            self.failed = True
            self.sidecar._status({**self.metadata, "capture_status": "failed",
                                  "mode": "stream", "error_type": type(exc).__name__})

    def finish(self, complete: bool) -> None:
        if self.finished:
            return
        self.finished = True
        try:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
            body = self.path.read_bytes()
            chunk_path = self.base.with_suffix(".chunks.jsonl")
            with chunk_path.open("x", encoding="utf-8") as output:
                for chunk in self.chunks:
                    output.write(json.dumps(chunk, sort_keys=True) + "\n")
            event_path = self.base.with_suffix(".events.jsonl")
            events = _stream_events(body)
            with event_path.open("x", encoding="utf-8") as output:
                for ordinal, event in enumerate(events, 1):
                    output.write(json.dumps({"ordinal": ordinal,
                        "raw_event_base64": base64.b64encode(event).decode("ascii")}) + "\n")
            termination, reasoning = _stream_result(body, consumed_to_eof=complete and not self.failed)
            self.sidecar._status({**self.metadata,
                "capture_status": "complete" if complete and not self.failed
                                  else "incomplete",
                "mode": "stream", "body_path": str(self.path), "body_bytes": len(body),
                "body_sha256": _sha(body), "chunks": len(self.chunks), "events": len(events),
                "response_id": _response_id(body),
                "stream_termination": termination, "reasoning_record_kind": reasoning})
        except Exception as exc:
            self.sidecar._status({**self.metadata, "capture_status": "failed",
                                  "mode": "stream", "error_type": type(exc).__name__})


class _TeeAsyncStream(httpx.AsyncByteStream):
    def __init__(self, inner: httpx.AsyncByteStream, writer: _StreamCapture):
        self.inner = inner
        self.writer = writer

    async def __aiter__(self):
        complete = False
        try:
            async for chunk in self.inner:
                self.writer.write(chunk)
                yield chunk
            complete = True
        finally:
            self.writer.finish(complete)

    async def aclose(self) -> None:
        try:
            await self.inner.aclose()
        finally:
            self.writer.finish(False)
