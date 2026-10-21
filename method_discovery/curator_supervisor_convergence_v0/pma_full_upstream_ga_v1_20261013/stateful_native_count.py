"""Private, model-matched native input count for the stateful candidate."""

import hashlib
import json
import re

import requests

from method_discovery.pma_stateful_memory_v1_20261021.budget import native_context_preflight


COUNT_FIELDS = frozenset({"model", "messages", "system", "tools", "tool_choice",
                          "thinking"})


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def count_projection(payload):
    """Use only fields accepted by the Messages count API, not generation metadata."""
    if not isinstance(payload, dict) or not isinstance(payload.get("model"), str):
        raise ValueError("invalid final generation payload")
    if not isinstance(payload.get("messages"), list):
        raise ValueError("invalid final generation messages")
    return {key: payload[key] for key in COUNT_FIELDS if key in payload}


class PrivateNativeCounter:
    def __init__(self, *, profile, window, record):
        if not isinstance(window, int) or window <= 0:
            raise ValueError("verified model context window required")
        if not profile.get("apikey") or not profile.get("apibase") or not profile.get("model"):
            raise ValueError("private model profile incomplete")
        self.profile = profile
        self.window = window
        self.record = record
        base = profile["apibase"].rstrip("/")
        if base.endswith("$"):
            raise ValueError("native count route cannot be derived from opaque endpoint")
        if base.endswith("/messages"):
            self.url = base + "/count_tokens"
        elif re.search(r"/v\d+(/|$)", base):
            self.url = base + "/messages/count_tokens"
        else:
            self.url = base + "/v1/messages/count_tokens"

    def __call__(self, payload):
        projection = count_projection(payload)
        if projection["model"] != self.profile["model"]:
            raise ValueError("native count model identity mismatch")
        payload_hash = hashlib.sha256(_canonical(payload)).hexdigest()
        count_hash = hashlib.sha256(_canonical(projection)).hexdigest()
        key = self.profile["apikey"]
        headers = {"Content-Type": "application/json",
                   "anthropic-version": "2023-06-01"}
        headers["x-api-key" if key.startswith("sk-ant-") else "authorization"] = (
            key if key.startswith("sk-ant-") else "Bearer " + key)
        self.record({"kind": "native_count_attempt", "payload_sha256": payload_hash,
                     "projection_sha256": count_hash, "model": projection["model"]})
        try:
            response = requests.post(self.url, json=projection, headers=headers,
                timeout=(5, 60))
            response.raise_for_status()
            value = response.json().get("input_tokens")
            if not isinstance(value, int) or value < 0:
                raise ValueError("native count response missing input_tokens")
            native_context_preflight(window=self.window, native_input_tokens=value,
                max_output_tokens=payload["max_tokens"])
        except BaseException as error:
            self.record({"kind": "native_count_failed", "payload_sha256": payload_hash,
                         "error_type": type(error).__name__})
            raise
        result = {"status": "accepted", "payload_sha256": payload_hash,
                  "projection_sha256": count_hash, "model": projection["model"],
                  "native_input_tokens": value, "max_output_tokens": payload["max_tokens"],
                  "safety_margin": 2048, "context_window_tokens": self.window}
        self.record({"kind": "native_count_accepted", **result})
        return result
