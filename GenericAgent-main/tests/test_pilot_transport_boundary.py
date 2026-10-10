"""No-network checks for the pilot's one-batch Supervisor transport."""

import threading
import time

import pytest

from monitor_agent_core.provider import (
    MonitorProviderClient, ProviderRecoveryExhausted, RetryableProviderError,
)


@pytest.mark.parametrize('failure', ['timeout', 'HTTP 429', 'HTTP 503'])
def test_one_batch_is_terminal_without_a_second_send(failure):
    client = object.__new__(MonitorProviderClient)
    client.recovery_deadline = time.monotonic() + 10
    client.recovery_stop = threading.Event()
    client.recovery_batches = 1
    sends = []

    def failed_batch(_tools):
        sends.append(failure)
        raise RetryableProviderError(failure)

    client._request_batch = failed_batch
    with pytest.raises(ProviderRecoveryExhausted):
        client._request_with_recovery([])
    assert sends == [failure]


@pytest.mark.parametrize('expired', [False, True])
def test_stop_or_deadline_blocks_the_first_send(expired):
    client = object.__new__(MonitorProviderClient)
    client.recovery_deadline = time.monotonic() - 1 if expired else time.monotonic() + 10
    client.recovery_stop = threading.Event()
    client.recovery_batches = 1
    if not expired:
        client.recovery_stop.set()
    sends = []
    client._request_batch = lambda _tools: sends.append(True)
    with pytest.raises(ProviderRecoveryExhausted):
        client._request_with_recovery([])
    assert not sends
