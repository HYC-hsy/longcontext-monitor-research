"""Pilot-only forwarding overlay for a byte-pinned existing Harbor GA adapter.

Loaded only by an explicitly selected research --agent path.  The ordinary
adapter, A condition and other experiments do not import this module.
"""

import hashlib
from pathlib import Path

from adapters import harbor_ga_agent as original


EXPECTED_ADAPTER_SHA256 = "8a4513c6b28befe747d581d22e94cd2715f20234c63115e0ea424a56d033c3a0"
FORWARD = (
    "GA_PMA_UPSTREAM_ENABLED",
    "GA_PMA_UPSTREAM_REQUESTS",
    "GA_PMA_UPSTREAM_RESPONSES",
    "GA_PMA_UPSTREAM_DEADLINE_EPOCH",
    "GA_PMA_CAPTURE_TASK_REQUESTS",
)

actual = hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest()
if actual != EXPECTED_ADAPTER_SHA256:
    raise RuntimeError("PMA Harbor base adapter byte identity mismatch")
if any(name in original.FORWARDED_ENV_VARS for name in FORWARD):
    raise RuntimeError("PMA Harbor forwarding unexpectedly already present")
original.FORWARDED_ENV_VARS = original.FORWARDED_ENV_VARS + FORWARD


class HarborGenericAgent(original.HarborGenericAgent):
    """Same original run/setup implementation, with only four extra env names."""

    @staticmethod
    def name() -> str:
        return "generic-agent-harbor-pma-upstream"
