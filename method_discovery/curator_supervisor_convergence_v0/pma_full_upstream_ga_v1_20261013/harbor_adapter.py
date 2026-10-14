"""Pilot-only forwarding overlay for a byte-pinned existing Harbor GA adapter.

Loaded only by an explicitly selected research --agent path.  The ordinary
adapter, A condition and other experiments do not import this module.
"""

import hashlib
from pathlib import Path

from adapters import harbor_ga_agent as original
from .networked_transport_setup import start_networked_transport


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
# This explicit research adapter is loaded in its own Harbor subprocess. The
# original run method reads this tuple; remove keys independently of network
# mode, without editing the external installed adapter or task profiles.
original.FORWARDED_ENV_VARS = tuple(
    name for name in original.FORWARDED_ENV_VARS if not name.endswith("_API_KEY")
) + FORWARD


class HarborGenericAgent(original.HarborGenericAgent):
    """Same original run/setup implementation, with only four extra env names."""

    @staticmethod
    def name() -> str:
        return "generic-agent-harbor-pma-upstream"

    async def setup(self, environment) -> None:
        await super().setup(environment)
        if __import__("os").environ.get("GA_RUN_ISOLATION") == "networked-host-keyed-v1":
            python_bin, _ = original._runtime_paths(self.python_home)
            await start_networked_transport(environment, python_bin, original.CONTAINER_GA)
