"""Use the unchanged authorized ASE entry with the fresh recovery identities."""

from method_discovery import uc_ase_entry as base
from method_discovery import uc_ase_v1_recovery_freeze as freeze

base.ROOT = freeze.ROOT
base.PLAN = freeze.PLAN
base.MANIFEST = freeze.MANIFEST
base.HARBOR_CLI = freeze.REPO / 'method_discovery/uc_ase_v1_harbor_cli.py'
base.COMMON_OVERRIDES = {'GA_MONITOR_DCEC': '0'}

load_authorized_slot = base.load_authorized_slot

if __name__ == '__main__':
    base.main()
