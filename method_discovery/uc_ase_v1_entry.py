"""Use the existing ASE authorization/bridge entry for the frozen v1-core pair."""

from method_discovery import uc_ase_entry as base
from method_discovery import uc_ase_v1_freeze as freeze


base.ROOT = freeze.ROOT
base.PLAN = freeze.PLAN
base.MANIFEST = freeze.MANIFEST
base.HARBOR_CLI = freeze.REPO / 'method_discovery/uc_ase_v1_harbor_cli.py'
base.COMMON_OVERRIDES = {'GA_MONITOR_DCEC': '0'}


def load_authorized_slot(run_id, authorization_path):
    return base.load_authorized_slot(run_id, authorization_path)


if __name__ == '__main__':
    base.main()
