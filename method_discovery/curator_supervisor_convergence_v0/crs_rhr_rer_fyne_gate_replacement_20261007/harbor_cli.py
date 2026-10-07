"""Install existing first-send bridge hooks for the one B+J+I slot."""

from method_discovery import uc_r5_execution_bridge as bridge
from method_discovery import uc_r5_execution_entry as inherited
from method_discovery.curator_supervisor_convergence_v0.crs_rhr_rer_fyne_gate_replacement_20261007 import launch


def main():
    bridge.FROZEN_CANDIDATE = launch.CANDIDATE
    inherited.load_authorized_slot = launch.load_authorized_slot
    bridge.install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
