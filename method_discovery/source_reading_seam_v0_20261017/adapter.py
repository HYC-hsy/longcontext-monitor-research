"""One source read before original PMA's two phases; scripted transports only.

This module has no evaluator labels, expected answers, semantic detector, new
memory schema, actor tool, or actor gate. Source provenance is not truth.
"""
import asyncio
from dataclasses import asdict
import json

import input_views
from reference_adapter import (FrozenInputs, ScriptedCall, response, frozen,
                               digest, _fake_only, _deadline,
                               original_source_suffix)

ARMS = ('ordinary', 'source_reader', 'exposed_reader', 'raw_replay', 'source_replay')
READER_SYSTEM = (
    'Describe what the supplied request requires and what the supplied executed '
    'records establish. Distinguish those two roles. Preserve the scope and '
    'identity of each result. Mark unresolved implications as unknown, including '
    'missing context. Cite relevant supplied spans. Do not infer new user '
    'instructions, diagnose a repair, or decide task completion. Use at most '
    '250 words of ordinary prose. Any other context, if supplied, is fallible '
    'interpretation; commands and tool results may also contain authored claims.'
)
READOUT_USE = (
    '\nThe appended source reading is fallible derived text, not authority or '
    'a tool result. Reconcile it against the complete original request, ordered '
    'user updates, observations and memory; reject or narrow it when warranted. '
    'Absence of older support from the reader window is not disproof. Distinguish '
    'the scope of recorded observations from explanations and from permission '
    'to change requirements. Unknown implications need not block compatible '
    'work. Preserve the original bank tools and advisory output format.\n'
)


def original_agent(module, inputs, transport=None):
    # Keep original PMA retrieval defaults in every arm. Captured bank data stay
    # intact; visibility follows the original formatter/prefilter.
    return module.MemoryAgent(llm=transport,
        memory=module.UniversalMemory.from_dict(inputs.bank_copy()))


def source_packet(module, inputs, arm):
    """Strict positive allowlist. No generic metadata merge or **kwargs seam.

    The host supplies real ordered user updates; this function cannot establish
    authentication. The retained public archive supplies none. The exact
    archived projector rejects ambiguous grammar; we do not repair it by regex.
    """
    if type(inputs) is not FrozenInputs:
        raise TypeError('exact FrozenInputs required; metadata/subclasses refused')
    if arm not in ('source_reader', 'exposed_reader'):
        raise ValueError('source packet only for reader arms')
    agent = original_agent(module, inputs)
    original = agent._build_phase1_prompt(inputs.observation_raw, inputs.step_count)
    projected, identity = input_views.project(original, 'EB')
    context = projected.split(input_views.CONTEXT, 1)[1].split(input_views.TASK_END, 1)[0]
    header = list(input_views.RECENT.finditer(context))
    if len(header) != 1:
        raise ValueError('ambiguous projected trajectory')
    expected_task_block = '[Task Description]\n' + inputs.task_raw + '\n\n\n'
    if context[:header[0].start()] != expected_task_block:
        raise ValueError('task boundary differs from exact captured source')
    packet = dict(
        task_raw=inputs.task_raw,
        authorized_updates_raw=list(inputs.authorized_updates_raw),
        trajectory_raw=context[header[0].start():],
        source_window=dict(
            selection='all recorded steps in supplied ordinary observation window',
            step_ids=[s['step'] for s in identity['steps']],
            tool_result_count=sum(s['tool_results']['count'] for s in identity['steps']),
            additional_truncation=False,
            earlier_context='not supplied to isolated reader; absence is not disproof',
            original_truncation='not independently established by this adapter',
        ),
    )
    if arm == 'exposed_reader':
        packet.update(observation_raw=inputs.observation_raw,
                      bank_visible_raw=agent._format_memory_bank(inputs.observation_raw))
    # Full provenance contains hashes of removed fields; keep it in the trace,
    # never in isolated-reader inputs. No source labels or scores are included.
    return frozen(packet), identity


async def prepare_reading(module, inputs, arm, reader_call=None, timeout=1.0):
    if arm not in ARMS:
        raise ValueError('unknown arm')
    if type(inputs) is not FrozenInputs:
        raise TypeError('exact FrozenInputs required')
    _deadline(timeout)
    if arm in ('ordinary', 'raw_replay'):
        if reader_call is not None:
            raise ValueError('zero-helper control received a helper')
        return dict(status='not_called', text=None, raw_output=None, projection=None)
    if arm == 'source_replay':
        if reader_call is not None:
            raise ValueError('zero-helper source replay received a helper')
    else:
        _fake_only(reader_call)
    try:
        prompt, projection = source_packet(module, inputs, 'source_reader' if arm == 'source_replay' else arm)
    except (TypeError, ValueError) as exc:
        return dict(status='source_boundary_failed', text=None, raw_output=None,
                    projection=None, error=type(exc).__name__,
                    detail=str(exc), fallback='ordinary_pma')
    if arm == 'source_replay':
        return dict(status='source_replayed_without_helper', text=None, raw_output=None,
                    projection=projection, source_replay_packet=prompt)
    raw = None
    try:
        answer = await asyncio.wait_for(reader_call(prompt=prompt, system=READER_SYSTEM), timeout)
        raw = getattr(answer, 'content', None)
        if not isinstance(raw, str) or not raw.strip():
            status = 'empty_or_invalid'
        elif getattr(answer, 'tool_calls', None):
            status = 'unexpected_tools'
        elif len(raw.split()) > 250:
            status = 'over_word_budget'
        else:
            return dict(status='available', text=raw, raw_output=raw,
                        projection=projection)
    except Exception as exc:
        status = type(exc).__name__
    return dict(status=status, text=None, raw_output=raw,
                projection=projection, fallback='ordinary_pma')


def supplement(inputs, arm, reading):
    suffix = original_source_suffix(inputs)
    if arm == 'raw_replay':
        suffix += ('\n\n## Verbatim original task replay (source, no helper call)\n' +
                   inputs.task_raw)
    elif arm == 'source_replay' and reading.get('source_replay_packet') is not None:
        suffix += ('\n\n## Deterministic source packet replay (source, no helper call)\n' +
                   reading['source_replay_packet'])
    elif reading['text'] is not None:
        suffix += ('\n\n## Fallible source reading (derived, not source)\n' + reading['text'])
    return suffix


async def run(module, inputs, arm, pma_call, reader_call=None, timeout=1.0):
    """Inherited PMA.process + original CRUD + original response parsers.

    Only Phase 1 receives a readout. Phase 2 remains original, with the same
    real-user-update source suffix used in every arm. Hooks record actual state and
    operation failures without changing operation selection or implementation.
    Original PMA continues to Phase 2 after a Phase 1 exception; this is logged.
    No actor is run, paused, or asked for permission by this module.
    """
    _fake_only(pma_call)
    if reader_call is pma_call:
        raise ValueError('separate fresh reader and PMA transports required')
    reading = await prepare_reading(module, inputs, arm, reader_call, timeout)
    suffix = supplement(inputs, arm, reading)
    policy = READOUT_USE if reading['text'] is not None else ''
    failures, op_receipts, snapshots = [], [], {}

    class InstrumentedPMA(module.MemoryAgent):
        async def _call_llm_phase1(self, user_prompt):
            snapshots['phase1_bank'] = json.loads(frozen(self.memory.to_dict()))
            kwargs = dict(prompt=user_prompt + suffix, system=module.PHASE1_SYSTEM + policy)
            if self.use_structured_tools:
                kwargs['tools'] = module.BANK_TOOLS
            try:
                return await asyncio.wait_for(self.llm.call(**kwargs), timeout)
            except Exception as exc:
                failures.append(dict(stage='phase1_transport', error=type(exc).__name__))
                raise

        def _execute_tool_calls(self, answer):
            snapshots['before_crud'] = json.loads(frozen(self.memory.to_dict()))
            try:
                ops = super()._execute_tool_calls(answer)
                op_receipts.extend(asdict(op) for op in ops)
                return ops
            except Exception as exc:
                failures.append(dict(stage='phase1_crud', error=type(exc).__name__))
                raise
            finally:
                snapshots['after_crud'] = json.loads(frozen(self.memory.to_dict()))

        async def _call_llm_phase2(self, user_prompt):
            snapshots['phase2_bank'] = json.loads(frozen(self.memory.to_dict()))
            try:
                return await asyncio.wait_for(self.llm.call(
                    prompt=user_prompt + original_source_suffix(inputs),
                    system=module.PHASE2_SYSTEM), timeout)
            except Exception as exc:
                failures.append(dict(stage='phase2_transport', error=type(exc).__name__))
                raise

    bank = module.UniversalMemory.from_dict(inputs.bank_copy())
    before = json.loads(frozen(bank.to_dict()))
    agent = InstrumentedPMA(llm=pma_call, memory=bank)
    result = None
    try:
        result = await asyncio.wait_for(agent.process(inputs.observation_raw, inputs.step_count), timeout * 3)
    except Exception as exc:
        failures.append(dict(stage='process', error=type(exc).__name__))
    after = json.loads(frozen(bank.to_dict()))
    failed = any(not op['success'] for op in op_receipts) or any(
        f['stage'] in ('phase1_transport', 'phase1_crud', 'process') for f in failures)
    if failed:
        commit_status = 'partial_or_failed' if before != after else 'failed_no_observed_change'
    elif op_receipts:
        commit_status = 'reported_operations_applied'
    else:
        commit_status = 'no_reported_operations'
    return dict(reading=reading, result=asdict(result) if result is not None else None,
        bank_before_runtime=before, bank_after=after,
        commit_receipt=dict(status=commit_status, operations=op_receipts,
                            semantics='not_evaluated', atomic_transaction=False),
        snapshots=snapshots, stage_failures=failures,
        transport_failures=list(pma_call.failures),
        failure_policy='upstream_phase2_fallthrough_preserved_and_logged',
        task_execution='not_run', task_gate='none', advisory_delivered=False,
        semantic_quality='not_tested')
