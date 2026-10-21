"""Offline o200k_base proxy counts, separate from native provider usage."""

from __future__ import annotations

import hashlib

from .source import ContractError, canonical


class TokenProxy:
    def __init__(self, input_limit: int = 32768) -> None:
        try:
            import tiktoken
        except ImportError as error:
            raise ContractError("tokenizer_unavailable", "o200k_base required") from error
        self.encoding = tiktoken.get_encoding("o200k_base")
        self.input_limit = input_limit
        fingerprint = hashlib.sha256()
        for piece, rank in sorted(self.encoding._mergeable_ranks.items()):
            fingerprint.update(len(piece).to_bytes(4, "big"))
            fingerprint.update(piece)
            fingerprint.update(rank.to_bytes(4, "big"))
        self.vocab_sha256 = fingerprint.hexdigest()
        self.version = tiktoken.__version__

    def measure(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {"messages": messages, "tools": tools or []}
        raw = canonical(payload)
        text = raw.decode("utf-8")
        tokens = len(self.encoding.encode(text, disallowed_special=()))
        return {"characters": len(text), "utf8_bytes": len(raw),
                "proxy_tokens": tokens, "proxy_encoding": "o200k_base",
                "proxy_package_version": self.version,
                "proxy_vocab_sha256": self.vocab_sha256}

    def enforce(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        usage = self.measure(messages, tools)
        if usage["proxy_tokens"] > self.input_limit:
            raise ContractError("input_budget_exceeded", str(usage["proxy_tokens"]))
        return usage


def native_context_preflight(*, window: int | None, native_input_tokens: int | None,
                             max_output_tokens: int, safety_margin: int = 2048) -> None:
    """No live request is allowed when the model-specific guard is unknown."""
    if window is None or native_input_tokens is None:
        raise ContractError("native_context_guard_unavailable")
    if native_input_tokens + max_output_tokens + safety_margin > window:
        raise ContractError("native_context_limit")
