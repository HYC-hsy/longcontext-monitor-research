"""Explicit PMA-pilot Harbor bootstrap; never installed in ordinary Harbor."""

from .pma_harbor_hooks import install_trial_hooks


def main() -> None:
    install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
