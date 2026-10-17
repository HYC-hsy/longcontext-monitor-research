"""Host-side one-task PMA worker; never installed inside the GA container."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace

from episode import PMAEpisode, construct_upstream
from event_spool import EventDispatcher
from memory_agent.memory_enabled_agent import MemoryEnabledTerminus2
from harbor.agents.terminus_2.terminus_2 import Terminus2


class PMAAuditIntegrityError(BaseException):
    """Must cross the upstream `except Exception` phase-silence handler."""


def append_private_audit(path: Path, row: dict) -> None:
    try:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True,
                                    default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception as exc:
        raise PMAAuditIntegrityError("private PMA audit write failed") from exc


def install_transport_audit(agent, archive: Path) -> None:
    """Observe the original two calls without changing its exception policy."""
    original = agent._memory_llm.call

    async def audited_call(*, prompt, system, tools=None):
        phase = "bank_management" if tools else "context_decision"
        started = time.time()
        status = "complete"
        append_private_audit(archive / "memory_payload.jsonl", {
            "phase": phase, "prompt": prompt, "system": system,
            "tools": tools, "started_epoch": started})
        try:
            return await original(prompt=prompt, system=system, tools=tools)
        except BaseException as exc:
            status = type(exc).__name__
            raise
        finally:
            append_private_audit(archive / "memory_transport.jsonl", {
                "phase": phase, "status": status,
                "started_epoch": started, "ended_epoch": time.time()})

    agent._memory_llm.call = audited_call


async def serve(args: argparse.Namespace) -> None:
    vendor = Path(__file__).resolve().parent / "vendor" / "pma_89e5c0d"
    sources = (Path(inspect.getfile(MemoryEnabledTerminus2)).resolve(),
               Path(inspect.getfile(Terminus2)).resolve())
    if (not sources[0].is_relative_to(vendor / "src") or
            not sources[1].is_relative_to(vendor / "external" / "harbor" / "src")):
        raise RuntimeError("PMA worker did not load both pinned upstream sources")
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
    profile = None
    profile_path = os.environ.get("PMA_MEMORY_PROFILE_FILE")
    if profile_path:
        raw_profile = Path(profile_path).resolve(strict=True).read_bytes()
        expected_hash = os.environ.get("PMA_MEMORY_PROFILE_SHA256")
        if not expected_hash or hashlib.sha256(raw_profile).hexdigest() != expected_hash:
            raise RuntimeError("PMA memory profile identity mismatch")
        profile = json.loads(raw_profile)["claude_monitor_opus48"]
    agent = construct_upstream(private / "upstream_agent",
                               memory_api_base=os.environ.get("PMA_MEMORY_API_BASE"),
                               memory_api_key=os.environ.get("PMA_MEMORY_API_KEY"),
                               memory_profile=profile,
                               research_candidate=getattr(args, "research_candidate", "U"))
    if args.fake_memory:
        from harbor.llms.base import LLMResponse

        async def offline_memory(*, prompt, system, tools=None):
            if tools:
                if getattr(args, "fake_memory_update", False) and "PMA_OFFLINE_TOOL_OK" in prompt:
                    call = SimpleNamespace(function=SimpleNamespace(
                        name="memory_save_knowledge", arguments={
                            "content": "Public tool returned PMA_OFFLINE_TOOL_OK"}))
                    return LLMResponse(content="", tool_calls=[call])
                return LLMResponse(content="", tool_calls=[])
            if getattr(args, "fake_memory_update", False) and "PMA_OFFLINE_TOOL_OK" not in prompt:
                return LLMResponse(content="<no_intervention/>")
            return LLMResponse(content="<context_for_action>Offline PMA reminder.</context_for_action>")

        agent._memory_llm.call = offline_memory
    episode = PMAEpisode(agent, run_id=args.run_id, task_id=args.task_id,
                         archive=private / "archive")
    install_transport_audit(agent, episode.archive)
    dispatcher = EventDispatcher(episode, requests, responses,
                                 deadline_epoch=args.deadline_epoch)
    (private / "worker_ready.json").write_text(json.dumps({
        "run_id": args.run_id, "task_id": args.task_id,
        "deadline_epoch": args.deadline_epoch, "fake_memory": args.fake_memory,
        "research_candidate": getattr(args, "research_candidate", "U")},
        sort_keys=True), encoding="utf-8")
    stopped = asyncio.Event()
    for name in ("SIGTERM", "SIGINT"):
        signum = getattr(signal, name, None)
        if signum is not None:
            try:
                asyncio.get_running_loop().add_signal_handler(signum, stopped.set)
            except (NotImplementedError, RuntimeError):
                pass
    reason = "task_end"
    active = None
    try:
        while not episode.ended:
            if stopped.is_set() or (private / "stop.request").exists():
                reason = "host_stop"
                break
            if time.time() >= args.deadline_epoch:
                reason = "deadline"
                break
            active = asyncio.create_task(dispatcher.serve_once())
            while not active.done():
                await asyncio.wait({active}, timeout=0.05)
                if (stopped.is_set() or (private / "stop.request").exists()
                        or time.time() >= args.deadline_epoch):
                    reason = "stopped_or_deadline_in_flight_unknown"
                    active.cancel()
                    break
            if reason != "task_end":
                break
            await active
            active = None
            await asyncio.sleep(0.05)
    except BaseException as exc:
        reason = f"worker_error:{type(exc).__name__}"
        raise
    finally:
        if not episode.ended:
            outcome = {"reason": reason, "task_end_received": False,
                       "remote_execution": "unknown" if active is not None else "not_in_flight"}
            try:
                outcome["local_save"] = episode.finalize_without_event(reason)
            except Exception as exc:
                outcome["local_save"] = {"status": "failed", "error_type": type(exc).__name__}
            (private / "worker_stopped_without_task_end.json").write_text(
                json.dumps(outcome, sort_keys=True), encoding="utf-8")
        (private / "worker_exit.json").write_text(json.dumps({
            "run_id": args.run_id, "task_id": args.task_id,
            "task_end_saved": episode.ended and reason == "task_end",
            "reason": reason, "ended_epoch": time.time()}, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--requests", required=True)
    parser.add_argument("--responses", required=True)
    parser.add_argument("--deadline-epoch", type=float, required=True)
    parser.add_argument("--fake-memory", action="store_true")
    parser.add_argument("--fake-memory-update", action="store_true")
    parser.add_argument("--research-candidate", choices=("U", "V1", "D1", "S", "R", "S2", "R2"), default="U")
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
