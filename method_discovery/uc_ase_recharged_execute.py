"""Run only the fresh recharged Kitex/Fyne pair using the prior serial policy."""

from method_discovery import uc_ase_execute as base
from method_discovery import uc_ase_recharged_entry as entry
from method_discovery import uc_ase_recharged_freeze as replacement


base.PLAN = replacement.base.PLAN
base.MANIFEST = replacement.base.MANIFEST
base.ROOT = replacement.base.ROOT
base.ORDER = replacement.base.ORDER
base.load_authorized_slot = entry.load_authorized_slot
base.ENTRY_MODULE = 'method_discovery.uc_ase_recharged_entry'


if __name__ == '__main__':
    raise SystemExit(base.main())
