"""Install existing first-send and terminal-capture hooks for the replacement."""

from method_discovery import uc_r5_execution_bridge as bridge
from method_discovery import uc_r5_execution_entry as inherited
from method_discovery.curator_supervisor_convergence_v0.fyne_gate_candidate_r2 import replacement_launch


def main():
    bridge.FROZEN_CANDIDATE = replacement_launch.base.CANDIDATE
    inherited.load_authorized_slot = replacement_launch.base.load_authorized_slot
    bridge.install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
