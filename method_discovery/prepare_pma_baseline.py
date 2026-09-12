"""Prepare a synchronous external baseline; does not launch a task or call an API."""
import argparse
import json
from clean_monitor_prepare_real_task_gate import build_manifest


def pma_environment(base):
    env = dict(base)
    env.update(GA_MONITOR_ENABLED='0', GA_PMA_ENABLED='1',
               GA_PMA_CONFIG='native_oai_cc_vibe_gpt56_sol_high',
               GA_PMA_ARTIFACT_DIR='/logs/agent/pma',
               GA_RUN_ISOLATION='no-network-unix-inference-v1',
               GA_CONDITION_ID='pma-sync-ga', GA_LLM_CONFIG_NAME='native_claude_cc_vibe_opus48')
    return env


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--run-suffix', required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.task_id, args.run_suffix)
    manifest['candidate'] = 'pma-sync-ga-adaptation'
    for run in manifest['runs']:
        run['condition'] = 'pma-sync-ga'
        run['environment'] = pma_environment(run['environment'])
    # No experiment-manifest path is baked into argv: this is a proposal only.
    manifest['status'] = 'proposal_requires_launch_gate'
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
