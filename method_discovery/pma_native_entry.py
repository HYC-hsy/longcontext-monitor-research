"""Explicit approved native trial; intended only inside the trusted controller."""
import argparse
import asyncio
import json
import re
from pathlib import Path
import socket
import subprocess
import sys
import time

from pma_native_support import original_config
from pma_native_trial import execute_trial

REFERENCE = Path('/workspace/some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-real-run', action='store_true')
    parser.add_argument('--task', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--task-image', required=True)
    parser.add_argument('--seconds', type=int, required=True)
    args = parser.parse_args()
    if not args.approved_real_run:
        parser.error('Separate real-run approval is required')
    if not re.fullmatch(r'(?:[^\s]+@)?sha256:[0-9a-f]{64}', args.task_image) or args.seconds <= 0:
        parser.error('Pinned task image and positive wall-time budget required')
    from harbor.models.task.task import Task
    task = Task(args.task)
    task.config.environment.docker_image = args.task_image
    config = original_config(REFERENCE)
    bridge = subprocess.Popen([sys.executable,
        str(Path(__file__).with_name('isolated_transport.py')), 'local'])
    try:
        for _ in range(100):
            if bridge.poll() is not None:
                raise RuntimeError('Local inference bridge exited')
            try:
                with socket.create_connection(('127.0.0.1', 18765), timeout=.1):
                    break
            except OSError:
                time.sleep(.1)
        else:
            raise TimeoutError('Local inference bridge did not start')
        out = Path(args.output)
        if out.exists():
            raise FileExistsError(out)
        result = asyncio.run(execute_trial(task, config, out, args.seconds, approved=True))
        print(json.dumps({'status': result['status'], 'output': str(out)}))
    finally:
        bridge.terminate()
        bridge.wait(timeout=10)


if __name__ == '__main__':
    main()
