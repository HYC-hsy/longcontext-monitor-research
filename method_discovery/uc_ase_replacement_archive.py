"""Archive only the executed prefix of the fresh ASE replacement batch."""

from method_discovery import uc_ase_archive as base
from method_discovery import uc_ase_replacement_freeze as replacement


base.ROOT = replacement.base.ROOT
base.PLAN = replacement.base.PLAN
base.CAMPAIGN = replacement.base.CAMPAIGN
base.RECORDS = base.ROOT / 'records'


if __name__ == '__main__':
    base.main()
