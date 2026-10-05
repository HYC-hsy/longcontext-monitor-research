"""Archive only the actually executed ASE-v1-core prefix, without any model call."""

from method_discovery import uc_ase_archive as base
from method_discovery import uc_ase_v1_freeze as freeze


base.ROOT = freeze.ROOT
base.PLAN = freeze.PLAN
base.CAMPAIGN = freeze.CAMPAIGN
base.RECORDS = base.ROOT / 'records'


if __name__ == '__main__':
    base.main()
