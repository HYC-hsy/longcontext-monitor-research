"""Campaign identity adapter for the unchanged research Harbor bridge hooks."""

import json

from method_discovery import uc_r5_execution_bridge as bridge
from method_discovery import uc_r5_execution_entry as inherited
from method_discovery import uc_root_scope_entry as campaign


def main():
    plan = json.loads(campaign.PLAN.read_text(encoding='utf-8'))
    bridge.FROZEN_CANDIDATE = plan['candidate_commit']
    inherited.load_authorized_slot = campaign.load_authorized_slot
    bridge.install_trial_hooks()
    from harbor.cli.main import app
    app()


if __name__ == '__main__':
    main()
