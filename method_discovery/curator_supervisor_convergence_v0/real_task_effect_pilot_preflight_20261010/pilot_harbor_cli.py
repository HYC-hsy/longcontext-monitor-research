"""Explicit, fail-closed Harbor subprocess bootstrap for the pilot only."""

from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_harbor_hooks import (
    install_trial_hooks,
)


def main():
    install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
