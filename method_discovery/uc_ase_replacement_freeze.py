"""Fresh identity replacement after the archived DCEC environment override failure."""

from pathlib import Path

from method_discovery import uc_ase_freeze as base


base.ROOT = base.REPO / 'method_discovery/runs/ase_v0_20261005/discovery_01_replacement'
base.PLAN = base.ROOT / 'PLAN.json'
base.MANIFEST = base.ROOT / 'RUNNER_MANIFEST.json'
base.PRIVATE = Path(r'E:\ase_v0_private_replacement_20261005')
base.CAMPAIGN = Path(r'E:\LongContext\long_context_bench\output\ase_v0_discovery_replacement_20261005')
base.ORDER = (
    ('ktx-0.13.0-roadmap', '9a8da7e53bb14380b533964c0c52f8a3'),
    ('fyn-2.2.0-roadmap', '550ad928d8dc481a9cc57c0f85593300'),
)
base.COMMON_OVERRIDES = {'GA_MONITOR_DCEC': '0'}
base.REPLACEMENT_PROVENANCE = {
    'prior_invalid_archive_commit': 'ab452235',
    'prior_run_id': 'fd962a22d2bc4af195d90e9de9ee34cd',
    'prior_stage': 'Supervisor startup after real Task requests',
    'reason': 'Inherited GA_MONITOR_DCEC=1 overrode ASE profile DCEC=false',
    'prior_fyne_started': False,
    'fresh_task_and_supervisor_sessions': True,
    'scientific_mechanism_commit_unchanged': base.MECHANISM,
    'authorization': 'User explicitly authorized configuration repair and fresh rerun',
}


def main():
    base.main()


if __name__ == '__main__':
    main()
