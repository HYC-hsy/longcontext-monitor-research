"""Host-side one-task PMA worker; never installed inside the GA container."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import signal

from episode import PMAEpisode, construct_upstream
from event_spool import EventDispatcher


async def serve(args: argparse.Namespace) -> None:
    private = Path(args.private_root).resolve(strict=False)
    requests = Path(args.requests).resolve(strict=True)
    responses = Path(args.responses).resolve(strict=True)
    shared_parent = requests.parent if requests.parent == responses.parent else None
    if (private.exists() or private.is_relative_to(requests)
            or private.is_relative_to(responses)
            or (shared_parent is not None and private.is_relative_to(shared_parent))):
        raise RuntimeError("PMA private root must be fresh and outside shared spool")
    if requests == responses or requests.is_symlink() or responses.is_symlink():
        raise RuntimeError("PMA spool identity invalid")
    private.mkdir(parents=True)
    agent = construct_upstream(private / "upstream_agent",
                               memory_api_base=os.environ.get("PMA_MEMORY_API_BASE"),
                               memory_api_key=os.environ.get("PMA_MEMORY_API_KEY"))
    episode = PMAEpisode(agent, run_id=args.run_id, task_id=args.task_id,
                         archive=private / "archive")
    dispatcher = EventDispatcher(episode, requests, responses)
    stopped = asyncio.Event()
    for name in ("SIGTERM", "SIGINT"):
        signum = getattr(signal, name, None)
        if signum is not None:
            try:
                asyncio.get_running_loop().add_signal_handler(signum, stopped.set)
            except (NotImplementedError, RuntimeError):
                pass
    while not stopped.is_set() and not episode.ended:
        await dispatcher.serve_once()
        await asyncio.sleep(0.05)
    # A fault or cancellation must not masquerade as normal task_end.
    if not episode.ended:
        (private / "worker_stopped_without_task_end").touch()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--responses", required=True)
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
