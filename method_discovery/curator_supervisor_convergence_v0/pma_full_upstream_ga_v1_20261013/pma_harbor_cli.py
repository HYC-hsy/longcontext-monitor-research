"""Explicit PMA-pilot Harbor bootstrap; never installed in ordinary Harbor."""

import sys

from .pma_harbor_hooks import install_trial_hooks


def main() -> None:
    if not (len(sys.argv) == 2 and sys.argv[1] in ('--help', '-h')):
        install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
