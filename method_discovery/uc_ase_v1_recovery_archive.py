"""Archive the actually executed fresh recovery prefix without another request."""

from method_discovery import uc_ase_archive as base
from method_discovery import uc_ase_v1_recovery_freeze as freeze

base.ROOT = freeze.ROOT
base.PLAN = freeze.PLAN
base.CAMPAIGN = freeze.CAMPAIGN
base.RECORDS = base.ROOT / 'records'

if __name__ == '__main__':
    base.main()
