"""Fresh ASE replacement launcher; delegates to the unchanged bridge path."""

from method_discovery import uc_ase_entry as base
from method_discovery import uc_ase_replacement_freeze as replacement


base.ROOT = replacement.base.ROOT
base.PLAN = replacement.base.PLAN
base.MANIFEST = replacement.base.MANIFEST
base.HARBOR_CLI = replacement.base.REPO / 'method_discovery/uc_ase_replacement_harbor_cli.py'
base.COMMON_OVERRIDES = replacement.base.COMMON_OVERRIDES


def load_authorized_slot(run_id, authorization_path):
    return base.load_authorized_slot(run_id, authorization_path)


def main():
    base.main()


if __name__ == '__main__':
    main()
