import threading
import time

import pytest

from monitor_agent_core.pause_lease import PauseLease


def test_unrequested_gate_does_not_wait():
    lease = PauseLease()
    started = time.monotonic()
    assert lease.wait()
    assert time.monotonic() - started < .1


def test_explicit_pause_and_release():
    lease = PauseLease()
    lease.request('wrong premise', 2)
    advanced = threading.Event()
    worker = threading.Thread(target=lambda: (lease.wait(), advanced.set()))
    worker.start()
    assert not advanced.wait(.03)
    assert lease.release()['was_active']
    assert advanced.wait(.5)
    worker.join()


def test_lease_expires_even_without_monitor():
    lease = PauseLease()
    lease.request('investigate', 1)
    started = time.monotonic()
    assert lease.wait()
    assert .8 <= time.monotonic() - started < 2


def test_user_stop_breaks_pause():
    lease = PauseLease()
    lease.request('investigate', 300)
    assert not lease.wait(lambda: True)


@pytest.mark.parametrize('reason,seconds', [('', 1), ('r', 0), ('r', 301), ('r', float('nan'))])
def test_invalid_pause_is_not_installed(reason, seconds):
    lease = PauseLease()
    with pytest.raises(ValueError):
        lease.request(reason, seconds)
    assert lease.wait()
