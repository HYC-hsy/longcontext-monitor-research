"""Serial, one-shot execution of only the authorized Kitex/Fyne ASE-v1-core pair."""

from method_discovery import uc_ase_execute as base
from method_discovery import uc_ase_v1_entry as entry
from method_discovery import uc_ase_v1_freeze as freeze


base.PLAN = freeze.PLAN
base.MANIFEST = freeze.MANIFEST
base.ROOT = freeze.ROOT
base.ORDER = freeze.ORDER
base.load_authorized_slot = entry.load_authorized_slot
base.ENTRY_MODULE = 'method_discovery.uc_ase_v1_entry'


if __name__ == '__main__':
    raise SystemExit(base.main())
