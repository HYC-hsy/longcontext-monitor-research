"""Run the fresh replacement Kitex/Fyne pair serially with existing stop rules."""

from method_discovery import uc_ase_execute as base
from method_discovery import uc_ase_replacement_entry as entry
from method_discovery import uc_ase_replacement_freeze as replacement


base.PLAN = replacement.base.PLAN
base.MANIFEST = replacement.base.MANIFEST
base.ROOT = replacement.base.ROOT
base.ORDER = replacement.base.ORDER
base.load_authorized_slot = entry.load_authorized_slot
base.ENTRY_MODULE = 'method_discovery.uc_ase_replacement_entry'


if __name__ == '__main__':
    raise SystemExit(base.main())
