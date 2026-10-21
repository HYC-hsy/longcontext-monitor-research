"""Private, model-matched native input count for the stateful candidate."""

import hashlib
import json
import re
import time
from datetime import datetime, timezone

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
        self.connect_timeout = max(1, int(profile.get('timeout',
            5 if profile.get('stream', True) else 10)))
        self.read_timeout = max(5, int(profile.get('read_timeout',
            40 if profile.get('stream', True) else 240)))
        proxy = profile.get('proxy')
        self.proxies = {'http': proxy, 'https': proxy} if proxy else None
        self.verify = profile.get('verify', True)
        base = profile["apibase"].rstrip("/")
        if base.endswith("$"):
            raise ValueError("native count route cannot be derived from opaque endpoint")
        if base.endswith("/messages"):
            self.url = base + "/count_tokens"
        elif re.search(r"/v\d+(/|$)", base):
            self.url = base + "/messages/count_tokens"
        else:
            self.url = base + "/v1/messages/count_tokens"
        self.endpoint_sha256 = hashlib.sha256(self.url.encode()).hexdigest()

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
        started = time.monotonic()
        started_at = datetime.now(timezone.utc).isoformat()
        self.record({"kind": "native_count_attempt", "payload_sha256": payload_hash,
                     "projection_sha256": count_hash, "model": projection["model"],
                     "endpoint_sha256": self.endpoint_sha256,
                     "started_at": started_at,
                     "connect_timeout_sec": self.connect_timeout,
                     "read_timeout_sec": self.read_timeout,
                     "timeout_source": "bound_profile.timeout/read_timeout",
                     "proxy_configured": self.proxies is not None,
                     "tls_verify_configured": self.verify is not False})
        response = None
        try:
            response = requests.post(self.url, json=projection, headers=headers,
                timeout=(self.connect_timeout, self.read_timeout),
                proxies=self.proxies, verify=self.verify)
            response.raise_for_status()
            value = response.json().get("input_tokens")
            if not isinstance(value, int) or value < 0:
                raise ValueError("native count response missing input_tokens")
            native_context_preflight(window=self.window, native_input_tokens=value,
                max_output_tokens=payload["max_tokens"])
        except BaseException as error:
            self.record({"kind": "native_count_failed", "payload_sha256": payload_hash,
                         "projection_sha256": count_hash,
                         "ended_at": datetime.now(timezone.utc).isoformat(),
                         "elapsed_seconds": round(time.monotonic() - started, 6),
                         "http_status": (response.status_code if response is not None
                                         else None), "error_type": type(error).__name__,
                         "private_error_repr": repr(error)})
            raise
        result = {"status": "accepted", "payload_sha256": payload_hash,
                  "projection_sha256": count_hash, "model": projection["model"],
                  "native_input_tokens": value, "max_output_tokens": payload["max_tokens"],
                  "safety_margin": 2048, "context_window_tokens": self.window,
                  "endpoint_sha256": self.endpoint_sha256,
                  "http_status": response.status_code,
                  "started_at": started_at,
                  "ended_at": datetime.now(timezone.utc).isoformat(),
                  "elapsed_seconds": round(time.monotonic() - started, 6)}
        self.record({"kind": "native_count_accepted", **result})
        return result
