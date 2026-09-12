"""Fail-closed task-side transport setup; no research or model policy."""
import shlex

ENVIRONMENT_NOTE = (
    '\n\n[Execution environment]\nThis run is offline. Public internet, '
    'reference solutions and prior-run artifacts are unavailable. Use the provided '
    'task, local repository, installed dependencies and execution evidence. '
    'Model inference is supplied separately; local tools remain available.')


async def start_isolated_transport(environment, python_bin, ga_dir):
    check = await environment.exec(
        "test -S /run/model-channel/gateway.sock && "
        "test \"$(ls /sys/class/net)\" = lo && "
        "test ! -S /var/run/docker.sock && "
        "test ! -f /opt/genericagent-source/mykey.py && "
        "test ! -d /opt/genericagent-source/temp && "
        "test ! -d /opt/genericagent-source/tests",
        timeout_sec=30, user='root')
    if check.return_code:
        raise RuntimeError('Task network/filesystem isolation check failed')
    start = await environment.exec(
        f"nohup {shlex.quote(python_bin)} {shlex.quote(ga_dir + '/isolated_transport.py')} local "
        '> /logs/agent/isolated_transport.log 2>&1 < /dev/null &',
        timeout_sec=30, user='root')
    if start.return_code:
        raise RuntimeError('Failed to start local inference socket transport')
    ready = await environment.exec(
        f"{shlex.quote(python_bin)} -c " + shlex.quote(
            "import socket,time\n"
            "for i in range(50):\n"
            " try:\n"
            "  s=socket.create_connection(('127.0.0.1',18765),1);s.close();break\n"
            " except OSError:time.sleep(.1)\n"
            "else:raise RuntimeError('Local inference transport not ready')"),
        timeout_sec=15, user='root')
    if ready.return_code:
        raise RuntimeError('Local inference transport readiness failed')
