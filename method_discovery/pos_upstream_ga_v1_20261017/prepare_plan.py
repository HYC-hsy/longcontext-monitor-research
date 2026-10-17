"""Read-only fixed-source PoS plan materialization; no Task or model execution."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import yaml

from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.export_official_evaluator import COMMIT
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.offline_launcher import image_identity
from method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.six_task_assets import descriptor

HERE = Path(__file__).resolve().parent
UPSTREAM_COMMIT = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'


def prepare(*, source, tasks, reference, output):
    source, reference, output = Path(source), Path(reference), Path(output)
    if not tasks or len(set(tasks)) != len(tasks):
        raise ValueError('provide unique serial Task IDs')
    historical = json.loads(reference.read_text(encoding='utf-8'))
    frozen = historical['config']
    if (historical['official_source_git_commit'] != COMMIT or
            frozen['task_turns_max'] != 300 or frozen['agent_wall_seconds'] != 14400 or
            frozen['task_profile_name'] != 'native_claude_cc_vibe_opus48'):
        raise RuntimeError('historical Task budget/profile identity differs')
    assets = {}
    for task in tasks:
        item = descriptor(source, task, registered=True)
        image = image_identity(item['image_tag'])
        matching = [value for value in image['repo_digests'] if value.startswith(
            item['image_tag'].rsplit(':', 1)[0] + '@sha256:')]
        if len(matching) != 1:
            raise RuntimeError(f'{task}: unique local official image digest missing')
        assets[task] = {**item, **image, 'repo_digest': matching[0]}
    fixed = yaml.safe_load((HERE / 'vendor' / 'configs' / 'loca' / 'pos.yaml').read_text(
        encoding='utf-8'))
    context = fixed['context']
    method_parameters = {key: fixed[key] for key in ('benchmark', 'method', 'harness',
                                                        'include_actions', 'max_json_retries')}
    method_parameters['context'] = {key: context[key] for key in (
        'type', 'task_mode', 'update_every_steps', 'agent_view',
        'diagnostic_progress_threshold', 'trapping', 'recovery')}
    method_parameters['context']['model'] = {
        'max_json_retries': context['model']['max_json_retries']}
    method_parameters['context']['sentinel'] = {key: context['sentinel'][key] for key in (
        'enabled', 'local_audit_every_steps', 'global_audit_every_steps',
        'recent_transition_count', 'consistency_enabled', 'progress_enabled')}
    method = {'name': 'released-core PoS-on-GA transfer',
              'upstream_commit': UPSTREAM_COMMIT,
              'task_turns_max': frozen['task_turns_max'],
              'agent_wall_seconds': frozen['agent_wall_seconds'],
              'harbor_whole_trial_retries': 0,
              'task_profile_name': frozen['task_profile_name'],
              'task_model_public': historical['resolved_models_public']['task'],
              'pos_roles': {'belief': 'same private Task profile, independent calls',
                            'consistency': 'same private Task profile, independent calls',
                            'progress': 'same private Task profile, independent calls'},
              'pos_role_max_tokens': {'belief': 4096, 'consistency': 512,
                                      'progress': 512},
              'pos_role_transport_retries': 0,
              'method_parameters': method_parameters,
              'network': frozen['network'], 'evaluation': frozen['evaluation']}
    plan = {'schema': 'pos-ga-serial-plan-v1', 'execution_authorized': False,
            'source_partition': 'observed_development_not_held_out',
            'official_source_git_commit': COMMIT, 'method': 'PoS',
            'planned_order': [{'order': n, 'task': task, 'condition': 'P'}
                              for n, task in enumerate(tasks, 1)]}
    manifest = {'schema': 'pos-ga-prepared-v1', 'status': 'prepared_not_executed',
                'execution_authorized': False, 'official_source_git_commit': COMMIT,
                'upstream_commit': UPSTREAM_COMMIT,
                'historical_config_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
                'method': method, 'assets': assets,
                'planned_order': plan['planned_order']}
    output.mkdir(parents=True, exist_ok=False)
    for name, value in (('plan.json', plan), ('manifest.json', manifest)):
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    return {'plan': str(output / 'plan.json'), 'manifest': str(output / 'manifest.json'),
            'tasks': tasks, 'execution_authorized': False}
