"""Fresh ASE pair after preserving the provider-billing failure; no model call."""

from pathlib import Path

from method_discovery import uc_ase_freeze as base


base.ROOT = base.REPO / 'method_discovery/runs/ase_v0_20261005/discovery_01_recharged'
base.PLAN = base.ROOT / 'PLAN.json'
base.MANIFEST = base.ROOT / 'RUNNER_MANIFEST.json'
base.PRIVATE = Path(r'E:\ase_v0_private_recharged_20261005')
base.CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\ase_v0_discovery_recharged_20261005')
base.ORDER = (
    ('ktx-0.13.0-roadmap', '641914afdc894019a434507bc0b59109'),
    ('fyn-2.2.0-roadmap', 'ccc6fc85c9124334af82b4e8a08c8037'),
)
base.COMMON_OVERRIDES = {'GA_MONITOR_DCEC': '0'}
base.REPLACEMENT_PROVENANCE = {
    'prior_invalid_archives': ['ab452235', 'discovery_01_replacement/records'],
    'prior_run_ids': ['fd962a22d2bc4af195d90e9de9ee34cd',
                      '9a8da7e53bb14380b533964c0c52f8a3'],
    'most_recent_failure': 'Provider HTTP 403 insufficient balance after real Supervisor requests',
    'prior_fyne_started': False,
    'fresh_task_and_supervisor_sessions': True,
    'scientific_mechanism_commit_unchanged': base.MECHANISM,
    'authorization': 'User explicitly reported recharge and authorized a fresh rerun',
}


if __name__ == '__main__':
    base.main()
