"""Fail-closed future replay entry. No authorization is shipped with this harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from .offline_replay import (CODE_IMAGE, FIXTURE, MODEL, ReplaySession, fixture_identity, sha)
from monitor_agent_core.provider import MonitorProviderClient


PROFILE_NAME = 'claude_monitor_opus48'
PRIVATE_PROFILE = Path(r'E:\crs_rhr_rer_fyne_high_budget_private_20261007\monitor_config\models.local.json')
PROFILE_SHA256 = '74c9ce480e8dee3823068a3fa32a67c1d4d99a2215d0ee909178e74911b1ee7b'
ARCHIVE_COMMIT = 'ca3648a925eb709deb09603e36e0f4981a03743a'


def validate_offline() -> dict:
    fixture = fixture_identity(FIXTURE)
    actual_image = subprocess.check_output(
        ['docker', 'image', 'inspect', CODE_IMAGE, '--format', '{{.Id}}'], text=True).strip()
    if actual_image != CODE_IMAGE:
        raise RuntimeError('Sanitized code-run image identity mismatch')
    if sha(PRIVATE_PROFILE) != PROFILE_SHA256:
        raise RuntimeError('Private profile file identity mismatch')
    profile = json.loads(PRIVATE_PROFILE.read_text(encoding='utf-8'))[PROFILE_NAME]
    if profile.get('model') != MODEL:
        raise RuntimeError('Reviewer model identity mismatch')
    return {'fixture': fixture, 'code_image': CODE_IMAGE, 'profile_file_sha256': PROFILE_SHA256,
            'profile': PROFILE_NAME, 'model': MODEL}


def run_one(condition: str, output: Path, authorization_path: Path) -> dict:
    if not authorization_path.is_file():
        raise RuntimeError('Independent replay authorization is absent')
    checked = validate_offline()
    authorization = json.loads(authorization_path.read_text(encoding='utf-8'))
    required = {'execution_authorized': True, 'archive_commit': ARCHIVE_COMMIT,
                'fixture_manifest_sha256': checked['fixture']['manifest_sha256'],
                'code_image': CODE_IMAGE, 'profile_file_sha256': PROFILE_SHA256, 'model': MODEL}
    if any(authorization.get(key) != value for key, value in required.items()):
        raise RuntimeError('Independent replay authorization identity mismatch')
    if condition not in authorization.get('approved_conditions', []):
        raise RuntimeError('Condition not independently authorized')
    profile = json.loads(PRIVATE_PROFILE.read_text(encoding='utf-8'))[PROFILE_NAME]
    client = MonitorProviderClient(PROFILE_NAME + '::fresh_release_review', profile)
    session = ReplaySession(condition, client, FIXTURE, output)
    return session.run(authorization)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--run', choices=['simple_fresh', 'spec_first_fresh'])
    parser.add_argument('--authorization', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.validate and args.run is None:
        print(json.dumps(validate_offline(), ensure_ascii=False))
        return
    if args.run is None or args.authorization is None or args.output is None:
        parser.error('--run requires --authorization and --output')
    result = run_one(args.run, args.output, args.authorization)
    print(json.dumps({key: result[key] for key in ('condition', 'status', 'model_turns', 'outcome')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
