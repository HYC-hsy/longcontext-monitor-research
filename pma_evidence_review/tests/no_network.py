"""Block network calls in fake tests, except Windows asyncio's local wakeup pair."""

import os
import socket
import sys
from unittest.mock import patch


def install_guard(test_case):
    original_connect = socket.socket.connect
    socketpair_code = getattr(getattr(socket, '_fallback_socketpair', None), '__code__', None)
    forbidden = []

    def guarded(sock, address):
        frame = sys._getframe(1)
        internal_pair = False
        if os.name == 'nt' and socketpair_code is not None:
            while frame is not None:
                if frame.f_code is socketpair_code:
                    internal_pair = True
                    break
                frame = frame.f_back
        if (internal_pair and isinstance(address, tuple) and address and
                address[0] in ('127.0.0.1', '::1')):
            return original_connect(sock, address)
        forbidden.append(address)
        raise AssertionError('network forbidden')

    guard = patch.object(socket.socket, 'connect', new=guarded)
    guard.start()
    test_case.addCleanup(lambda: test_case.assertEqual(forbidden, []))
    test_case.addCleanup(guard.stop)
