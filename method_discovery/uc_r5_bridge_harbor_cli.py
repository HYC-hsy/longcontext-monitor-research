"""Fail-closed Harbor CLI bootstrap for an explicitly authorized trial.

Unlike sitecustomize, an installation exception here terminates the CLI.
The normal Harbor Typer application still creates and executes the trial.
"""
from method_discovery.uc_r5_execution_bridge import install_trial_hooks


def main() -> None:
    install_trial_hooks()
    from harbor.cli.main import app

    app()


if __name__ == "__main__":
    main()
