"""Bind the existing research bridge to the one authorized Curator Fyne slot."""

from method_discovery import uc_r5_execution_bridge as bridge
from method_discovery import uc_r5_execution_entry as inherited
from method_discovery.curator_supervisor_convergence_v0.fyne_gate_candidate_r1 import launch


def main():
    bridge.FROZEN_CANDIDATE = launch.CANDIDATE
    inherited.load_authorized_slot = launch.load_authorized_slot
    bridge.install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
