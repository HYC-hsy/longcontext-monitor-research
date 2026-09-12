"""Native PMA/Terminus2 trial lifecycle; no implicit launch or model substitution.

Uses author's agent factory, Docker environment and post-run Verifier. The task
container has no network; the native agent's LiteLLM runs in the host controller.
This is NOT the Clean Monitor Unix-inference deployment profile.
"""
import asyncio
import json
import os
from pathlib import Path
import uuid


async def execute_trial(task, config, output, time_limit, *, approved=False,
                        environment_factory=None, agent_factory=None, verifier_factory=None):
    if not approved:
        raise PermissionError('Native PMA requires its own real-start approval')
    if os.name == 'nt' and agent_factory is None:
        raise RuntimeError('Unmodified native Harbor requires a Linux controller; Windows is fixture-only')
    if time_limit <= 0:
        raise ValueError('An explicit positive wall-time limit is required')
    # This adapter only supports audited prebuilt, single-container tasks.
    if not task.config.environment.docker_image:
        raise ValueError('Native preflight requires a pinned prebuilt task image')
    if (task.paths.environment_dir / 'docker-compose.yaml').exists():
        raise ValueError('Custom task networks require separate isolation review')
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.models.agent.context import AgentContext
    from harbor.models.trial.paths import TrialPaths
    from harbor.verifier.verifier import Verifier
    from memory_agent.runner import create_agent
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    paths = TrialPaths(trial_dir=output)
    paths.mkdir()
    if config is not None:
        declared = config.model_dump(mode='json')
        for side in ('model', 'memory'):
            declared[side].pop('api_key', None)
        (output / 'effective_config.json').write_text(json.dumps(declared, indent=2), encoding='utf-8')
    env_config = task.config.environment.model_copy(update={'allow_internet': False})
    environment = (environment_factory or DockerEnvironment)(
        environment_dir=task.paths.environment_dir, environment_name=task.name,
        session_id='pma-native-' + uuid.uuid4().hex[:12], trial_paths=paths,
        task_env_config=env_config)
    report = {'status': 'starting', 'reward': None, 'evaluation_status': 'not_started',
              'deployment': 'native-host-controller-offline-docker',
              'upstream_agent_unchanged': True, 'task_network': 'none'}
    agent = None
    try:
        await environment.start(force_build=False)
        check = await environment.exec(
            "test \"$(ls /sys/class/net)\" = lo && test ! -e /var/run/docker.sock && test ! -e /tests/test.sh",
            timeout_sec=30)
        if check.return_code:
            raise RuntimeError('Task network/hidden-tests preflight failed')
        agent = (agent_factory or create_agent)(config, paths.agent_dir)
        from pma_native_support import attach_usage
        attach_usage(agent, output)
        report['model_call_log'] = 'model_calls.jsonl'
        report['usage_scope'] = 'returned logical calls; internal retry usage may be unavailable'
        await agent.setup(environment)
        context = AgentContext()
        try:
            await asyncio.wait_for(agent.run(task.instruction, environment, context), time_limit)
            report['status'] = 'agent_finished'
        except asyncio.TimeoutError:
            # wait_for cancels and awaits the agent coroutine before evaluation.
            report['status'] = 'agent_timeout'
        report['task_usage'] = context.model_dump(mode='json')
        if hasattr(agent, 'save_memory'):
            agent.save_memory(str(output / 'memory.json'))
        # Only now upload hidden tests. No agent can run after this point.
        try:
            verdict = await asyncio.wait_for((verifier_factory or Verifier)(
                task=task, trial_paths=paths, environment=environment).verify(),
                task.config.verifier.timeout_sec)
            report.update(evaluation_status='completed', verifier=verdict.model_dump(mode='json'))
            report['reward'] = report['verifier'].get('rewards')
        except Exception as exc:
            report.update(evaluation_status='failed', evaluation_error_type=type(exc).__name__)
    except Exception as exc:
        report.update(status='engineering_failed', error_type=type(exc).__name__)
        raise
    finally:
        try:
            if agent is not None and hasattr(agent, 'save_memory'):
                agent.save_memory(str(output / 'memory.json'))
        finally:
            try:
                # Upstream delete=True also removes shared task images (--rmi all).
                # Ordinary down removes this fixture's containers, not cached images.
                await environment.stop(delete=False)
            except Exception as exc:
                report['cleanup_error_type'] = type(exc).__name__
            (output / 'native_result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
