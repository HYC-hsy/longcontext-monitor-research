"""Fresh ASE launcher following the archived provider-billing failure."""

from method_discovery import uc_ase_entry as base
from method_discovery import uc_ase_recharged_freeze as replacement


base.ROOT = replacement.base.ROOT
base.PLAN = replacement.base.PLAN
base.MANIFEST = replacement.base.MANIFEST
base.HARBOR_CLI = replacement.base.REPO / 'method_discovery/uc_ase_recharged_harbor_cli.py'
base.COMMON_OVERRIDES = replacement.base.COMMON_OVERRIDES


def load_authorized_slot(run_id, authorization_path):
    return base.load_authorized_slot(run_id, authorization_path)


if __name__ == '__main__':
    base.main()
