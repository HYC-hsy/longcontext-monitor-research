"""Offline o200k_base proxy counts, separate from native provider usage."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile

from .source import ContractError, canonical


class TokenProxy:
    _VOCAB_URL = "https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
    _VOCAB_SHA256 = "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"

    def __init__(self, input_limit: int | None = None) -> None:
        if input_limit is not None and (type(input_limit) is not int or input_limit < 1):
            raise ValueError("input_limit must be a positive integer or None")
        self.input_limit = input_limit
        self.encoding = None
        self.version = None
        self.vocab_sha256 = None
        self.unavailable_reason = None
        try:
            import tiktoken
            from tiktoken.registry import ENCODINGS
            if "o200k_base" not in ENCODINGS:
                cache_dir = (os.environ.get("TIKTOKEN_CACHE_DIR") or
                             os.environ.get("DATA_GYM_CACHE_DIR") or
                             str(Path(tempfile.gettempdir()) / "data-gym-cache"))
                cache_key = hashlib.sha1(self._VOCAB_URL.encode()).hexdigest()
                cache_path = Path(cache_dir) / cache_key
                if not cache_path.is_file() or hashlib.sha256(
                        cache_path.read_bytes()).hexdigest() != self._VOCAB_SHA256:
                    raise FileNotFoundError("verified local o200k_base cache unavailable")
            self.encoding = tiktoken.get_encoding("o200k_base")
            self.version = tiktoken.__version__
        except (ImportError, OSError, ValueError) as error:
            self.unavailable_reason = type(error).__name__
            if input_limit is not None:
                raise ContractError("tokenizer_unavailable", self.unavailable_reason) from error
            return
        fingerprint = hashlib.sha256()
        for piece, rank in sorted(self.encoding._mergeable_ranks.items()):
            fingerprint.update(len(piece).to_bytes(4, "big"))
            fingerprint.update(piece)
            fingerprint.update(rank.to_bytes(4, "big"))
        self.vocab_sha256 = fingerprint.hexdigest()

    def measure(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {"messages": messages, "tools": tools or []}
        raw = canonical(payload)
        text = raw.decode("utf-8")
        tokens = None
        reason = self.unavailable_reason
        if self.encoding is not None:
            try:
                tokens = len(self.encoding.encode(text, disallowed_special=()))
            except Exception as error:
                reason = f"proxy_encoding_failed:{type(error).__name__}"
                if self.input_limit is not None:
                    raise ContractError("tokenizer_unavailable", reason) from error
        return {"characters": len(text), "utf8_bytes": len(raw),
                "proxy_tokens": tokens, "proxy_encoding": "o200k_base",
                "proxy_unavailable_reason": reason if tokens is None else None,
                "proxy_package_version": self.version,
                "proxy_vocab_sha256": self.vocab_sha256}

    def enforce(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        usage = self.measure(messages, tools)
        if self.input_limit is not None and usage["proxy_tokens"] > self.input_limit:
            raise ContractError("input_budget_exceeded", str(usage["proxy_tokens"]))
        return usage


def native_context_preflight(*, window: int | None, native_input_tokens: int | None,
                             max_output_tokens: int, safety_margin: int = 2048) -> None:
    """No live request is allowed when the model-specific guard is unknown."""
    if window is None or native_input_tokens is None:
        raise ContractError("native_context_guard_unavailable")
    if native_input_tokens + max_output_tokens + safety_margin > window:
        raise ContractError("native_context_limit")
