"""Verify copied RSH raw bytes and scan archived material for private headers."""

from method_discovery import uc_dcm_integrity as inherited
from method_discovery.uc_rsh_freeze import ROOT, CAMPAIGN, PLAN


def main():
    inherited.ROOT = ROOT
    inherited.CAMPAIGN = CAMPAIGN
    inherited.PLAN = PLAN
    inherited.main()


if __name__ == '__main__':
    main()
