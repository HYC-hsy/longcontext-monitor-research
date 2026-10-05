"""Archive only the actually executed recharged ASE prefix."""

from method_discovery import uc_ase_archive as base
from method_discovery import uc_ase_recharged_freeze as replacement


base.ROOT = replacement.base.ROOT
base.PLAN = replacement.base.PLAN
base.CAMPAIGN = replacement.base.CAMPAIGN
base.RECORDS = base.ROOT / 'records'


if __name__ == '__main__':
    base.main()
