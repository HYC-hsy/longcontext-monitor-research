"""Install the unchanged first-send and terminal-capture hooks for this slot."""

from method_discovery import uc_r5_execution_bridge as bridge
from method_discovery import uc_r5_execution_entry as inherited
from method_discovery.curator_supervisor_convergence_v0.fyne_measurement_v01_r1 import launch


def main():
    bridge.FROZEN_CANDIDATE = launch.base.CANDIDATE
    inherited.load_authorized_slot = launch.base.load_authorized_slot
    bridge.install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == "__main__":
    main()
