"""Actual pinned worker lifecycle, in-process synthetic memory only."""
import asyncio, json, os, socket, tempfile, time
from pathlib import Path
from types import SimpleNamespace
import worker_main
import pytest
from event_spool import EventClient, SpoolError
from memory_agent.memory.context_predictive_memory_agent import PMAPhaseError

async def exercise(fail, root, monkeypatch):
    req=root/'spool'/'requests'; res=root/'spool'/'responses'
    req.mkdir(parents=True);res.mkdir()
    private=root/'private'
    args=SimpleNamespace(deadline_epoch=time.time()+30,research_candidate='pma_predictive_read_context_v1',
        private_root=str(private),requests=str(req),responses=str(res),run_id='synthetic-review',task_id='synthetic-task',
        pma_batch_rounds=8,citation_review_gate=None,citation_review_strategy=None,fake_memory=not fail,fake_memory_update=True)
    original_construct=worker_main.construct_upstream
    if fail:
        def construct(*a,**kw):
            agent=original_construct(*a,**kw)
            async def failing(*,prompt,**kwargs):
                if prompt.startswith('<task_description>\n'):
                    return SimpleNamespace(content='',tool_calls=[SimpleNamespace(id='saved',function=SimpleNamespace(name='memory_add',arguments={'content':'partially saved'}))])
                raise RuntimeError('synthetic provider failure')
            agent._memory_llm.call=failing
            return agent
        monkeypatch.setattr(worker_main, "construct_upstream", construct)
    client=EventClient(req,res,args.run_id,args.task_id,deadline_monotonic=time.monotonic()+30,worker_exit=private/'worker_exit.json')
    task=asyncio.create_task(worker_main.serve(args))
    async def exchange(kind,**fields):return await asyncio.to_thread(client.exchange,kind,**fields)
    if fail:
        try:await exchange('task_start',initial_user_content='Exact immutable task',pma_batch_rounds=8)
        except SpoolError:pass
        else:raise AssertionError('Failed wake generated successful event receipt')
        try:await task
        except PMAPhaseError:pass
        else:raise AssertionError('Worker failure did not propagate')
        audit=private/'archive'
        bank=json.loads((audit/'memory.json').read_text())
        assert len(bank['knowledge'])==1
        steps=json.loads((audit/'trajectory_memory.json').read_text())['steps']
        assert not steps
        rows=[json.loads(x) for x in (audit/'memory_tool_results.jsonl').read_text().splitlines()]
        assert len(rows)==1 and json.loads(rows[0]['tool_results'][0]['content'])['success']
        exit=json.loads((private/'worker_exit.json').read_text())
        assert exit['failure']['phase']=='unified' and exit['failure']['decision_produced'] is False
        assert not exit['task_end_saved']
    else:
        out=await exchange('task_start',initial_user_content='Exact immutable task',pma_batch_rounds=8)
        assert out['triggered']
        for n in range(1,10):
            before=await exchange('before_actor_call',actor_attempt=n)
            assert bool(before['reminder'])==(n in (1,9))
            out=await exchange('actor_step',actor_attempt=n,step_status='normal',public_input=[],public_blocks=[{'type':'text','text':f'round-{n}'}],public_results=[])
            assert out['triggered']==(n==8)
        await exchange('task_end',terminal='synthetic-finished')
        await task
        audit=private/'archive'
        requests=[json.loads(x) for x in (audit/'memory_payload.jsonl').read_text().splitlines()]
        assert len(requests)==2 and all(x['phase']=='unified_memory' for x in requests)
        bank=json.loads((audit/'memory.json').read_text())
        assert len(bank['knowledge'])==2
        steps=json.loads((audit/'trajectory_memory.json').read_text())['steps']
        assert len(steps)==2 and all(x['loop_mode']=='unified' and len(x['loop_rounds'])==1 for x in steps)
        assert all(x['raw_response_phase2']==x['user_prompt_phase2']=='' for x in steps)
        assert json.loads((private/'worker_exit.json').read_text())['task_end_saved']
    print(json.dumps({'case':'failure' if fail else 'success','status':'passed','path':str(root)}))


@pytest.mark.parametrize('fail', [False, True])
def test_actual_worker_lifecycle(tmp_path, monkeypatch, fail):
    for key in ('PMA_MEMORY_PROFILE_FILE', 'PMA_MEMORY_PROFILE_SHA256',
                'PMA_MEMORY_API_BASE', 'PMA_MEMORY_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    original_connect = socket.socket.connect
    original_socketpair = socket.socketpair
    def blocked(*args, **kwargs):
        raise AssertionError('Offline lifecycle test attempted network access')
    def local_socketpair(*args, **kwargs):
        with monkeypatch.context() as local:
            local.setattr(socket.socket, 'connect', original_connect)
            return original_socketpair(*args, **kwargs)
    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    monkeypatch.setattr(socket, 'socketpair', local_socketpair)
    asyncio.run(exercise(fail, tmp_path, monkeypatch))
