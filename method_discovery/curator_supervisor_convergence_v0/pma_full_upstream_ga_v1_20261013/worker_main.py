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
    calls = 0

    async def audited_call(*, prompt, system, tools=None):
        nonlocal calls
        calls += 1
        candidate_agent = agent._memory_agent
        phase = (candidate_agent.transport_phase if getattr(agent, '_research_candidate', None)
                 in ('pma_gap_memory_v0', 'pma_gap_evidence_v1') else "bank_management" if tools else "context_decision")
        started = time.time()
        status = "complete"
        append_private_audit(archive / "memory_payload.jsonl", {
            "phase": phase, "prompt": prompt, "system": system,
            "tools": tools, "started_epoch": started,
            "cycle_step": getattr(candidate_agent, '_step', None), "call_sequence": calls})
        try:
            response = await original(prompt=prompt, system=system, tools=tools)
            if getattr(agent, '_research_candidate', None) in ('pma_gap_memory_v0', 'pma_gap_evidence_v1'):
                append_private_audit(archive / 'gap_visible_transport.jsonl', {
                    'phase': phase, 'call_sequence': calls,
                    'cycle_step': getattr(candidate_agent, '_step', None),
                    'content': getattr(response, 'content', None),
                    'tool_calls': getattr(response, 'tool_calls', None)})
            return response
        except BaseException as exc:
            status = type(exc).__name__
            raise
        finally:
            append_private_audit(archive / "memory_transport.jsonl", {
                "phase": phase, "status": status,
                "started_epoch": started, "ended_epoch": time.time()})

    agent._memory_llm.call = audited_call


def fake_evidence_gap_arguments(candidate_agent, prompt):
    """Fixture-only selection from actual displayed P1 sources, never invented IDs."""
    parts = candidate_agent._parts
    if parts is None or parts.text != prompt:
        raise RuntimeError('fake evidence fixture has no bound P1 request')
    for handle, visible in parts.catalog.items():
        if visible.snapshot.record.source_kind != 'public':
            continue
        text = visible.snapshot.blob.text
        for start, end in visible.visible_spans:
            quote = text[start:end]
            if quote and text.count(quote) == 1:
                return {'content': 'Confirm the synthetic task result before completion.',
                        'evidence': [{'source': handle, 'quote': quote}]}
    raise RuntimeError('fake evidence fixture has no uniquely visible public source')


async def serve(args: argparse.Namespace) -> None:
    if args.deadline_epoch is None and args.research_candidate not in ('pma_gap_memory_v0', 'pma_gap_evidence_v1'):
        raise RuntimeError('uncapped PMA worker requires gap candidate identity')
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
                               research_candidate=getattr(args, "research_candidate", "U"),
                               citation_review_gate=getattr(args,"citation_review_gate",None),
                               citation_review_strategy=getattr(args,"citation_review_strategy",None))
    if args.fake_memory:
        from harbor.llms.base import LLMResponse

        gate_fixture_reviews={}
        async def offline_memory(*, prompt, system, tools=None):
            if args.research_candidate in ('pma_gap_memory_v0', 'pma_gap_evidence_v1'):
                phase = agent._memory_agent.transport_phase
                if phase == 'maintenance':
                    calls = []
                    if agent._memory_agent._step == 1:
                        arguments = (fake_evidence_gap_arguments(agent._memory_agent, prompt)
                            if args.research_candidate == 'pma_gap_evidence_v1' else
                            {'content': 'Confirm the synthetic task result before completion.'})
                        calls.append(SimpleNamespace(function=SimpleNamespace(
                            name='memory_save_gap', arguments=arguments)))
                    if getattr(args,'citation_review_gate',None):
                        if calls:
                            original=calls[0].function.arguments
                            calls=[SimpleNamespace(function=SimpleNamespace(name='memory_save_gap',arguments={**original,'content':text}))
                                   for text in ('GATE_FIXTURE_ACCEPTED','GATE_FIXTURE_REJECTED','GATE_FIXTURE_REPAIRABLE')]
                        return LLMResponse(content='GATE_FIXTURE_MAINTENANCE_RESPONSE',tool_calls=calls)
                    return LLMResponse(content='', tool_calls=calls)
                if phase == 'citation_review':
                    # Finite engineering fixture only: fixed labels, no semantic inference.
                    from citation_gate_config import CLAIM_SPLIT
                    if getattr(args,'citation_review_strategy',None)==CLAIM_SPLIT:
                        if prompt.startswith('CLOSED MATERIAL (A is not evidence):\n'):
                            material=json.loads(prompt.split('\n',1)[1])
                            op=material['original_operation'];text=op['content']
                            return LLMResponse(content=json.dumps({'op_index':op['op_index'],
                                'claims':[{'claim':text+' synthetic clause '+str(i),
                                    'original_text':text,'start':0,'end':len(text)} for i in (1,2)]}))
                        material=json.loads(prompt.split('\n',1)[1].split(
                            '\nSUBMITTED EVIDENCE ONLY (unchanged B):\n',1)[0])
                        op=material['original_operation']
                        verdict=('supported' if op['content'] in (
                            'GATE_FIXTURE_ACCEPTED','GATE_FIXTURE_REPAIRED') else 'insufficient')
                        return LLMResponse(content=json.dumps({'results':[
                            {'claim_index':claim['index'],'verdict':verdict,'evidence_ids':['E1'],
                             'original_fragment':claim['original_text'],
                             'explanation':'GATE_FIXTURE_REVIEW_CONTROL_ONLY'}
                            for claim in material['all_claims']],
                            'decomposition_complete':True,'coverage_original_fragment':'',
                            'coverage_explanation':'GATE_FIXTURE_REVIEW_CONTROL_ONLY'}))
                    material=json.loads(prompt.split('\n',1)[1].split('\nOUTPUT')[0])
                    op=material['original_operation'];index=op['op_index']
                    gate_fixture_reviews[index]=gate_fixture_reviews.get(index,0)+1
                    verdict=('supported' if op['content'] in ('GATE_FIXTURE_ACCEPTED','GATE_FIXTURE_REPAIRED') else 'insufficient')
                    return LLMResponse(content=json.dumps({'op_index':index,
                        'verdict':verdict,'explanation':'GATE_FIXTURE_REVIEW_CONTROL_ONLY'}))
                if phase == 'citation_repair':
                    original=json.loads(prompt)['original_arguments']
                    value=({'decision':'replace','content':'GATE_FIXTURE_REPAIRED','evidence':original['evidence']}
                           if original['content']=='GATE_FIXTURE_REPAIRABLE' else {'decision':'withdraw'})
                    return LLMResponse(content=json.dumps(value))
                if phase == 'selection':
                    return LLMResponse(content=(
                        '<context_for_action>Verify the synthetic result.</context_for_action>'
                        if agent._memory_agent._step == 1 else '<no_intervention/>'))
                raise RuntimeError('unexpected gap fake role')
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
        "research_candidate": getattr(args, "research_candidate", "U"),
        **({"citation_review_gate":args.citation_review_gate} if getattr(args,"citation_review_gate",None) else {}),
        **({"citation_review_strategy":args.citation_review_strategy} if getattr(args,"citation_review_strategy",None) else {})},
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
            if args.deadline_epoch is not None and time.time() >= args.deadline_epoch:
                reason = "deadline"
                break
            active = asyncio.create_task(dispatcher.serve_once())
            while not active.done():
                await asyncio.wait({active}, timeout=0.05)
                if (stopped.is_set() or (private / "stop.request").exists()
                        or (args.deadline_epoch is not None and time.time() >= args.deadline_epoch)):
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
    parser.add_argument("--deadline-epoch", type=lambda value: None if value == 'uncapped' else float(value), required=True)
    parser.add_argument("--fake-memory", action="store_true")
    parser.add_argument("--fake-memory-update", action="store_true")
    parser.add_argument("--citation-review-gate",choices=('gate-only','gate-one-repair'))
    from citation_gate_config import STRATEGIES
    parser.add_argument('--citation-review-strategy',choices=STRATEGIES)
    parser.add_argument("--research-candidate", choices=("U", "V1", "D1", "S", "R", "S2", "R2", "pma_gap_memory_v0", "pma_gap_evidence_v1"), default="U")
    asyncio.run(serve(parser.parse_args()))


if __name__ == "__main__":
    main()
