"""Pilot-only local inference transport under official Task networking.

The fixed Unix socket gateway and route contract are unchanged. This differs
from isolated_setup only in not requiring a loopback-only network namespace.
"""

from __future__ import annotations

import shlex


async def start_networked_transport(environment, python_bin: str, ga_dir: str) -> None:
    check = await environment.exec(
        "test -S /run/model-channel/gateway.sock && "
        "test ! -S /var/run/docker.sock && "
        "test ! -f /opt/genericagent-source/mykey.py && "
        "test ! -d /opt/genericagent-source/temp && "
        "test ! -d /opt/genericagent-source/tests",
        timeout_sec=30, user="root")
    if check.return_code:
        raise RuntimeError("Task model socket or credential boundary failed")
    started = await environment.exec(
        f"nohup {shlex.quote(python_bin)} "
        f"{shlex.quote(ga_dir + '/isolated_transport.py')} local "
        "> /logs/agent/isolated_transport.log 2>&1 < /dev/null &",
        timeout_sec=30, user="root")
    if started.return_code:
        raise RuntimeError("Task local inference transport failed to start")
    ready = await environment.exec(
        f"{shlex.quote(python_bin)} -c " + shlex.quote(
            "import socket,time\n"
            "for i in range(50):\n"
            " try:\n"
            "  s=socket.create_connection(('127.0.0.1',18765),1);s.close();break\n"
            " except OSError:time.sleep(.1)\n"
            "else:raise RuntimeError('Local inference transport not ready')"),
        timeout_sec=15, user="root")
    if ready.return_code:
        raise RuntimeError("Task local inference transport readiness failed")
