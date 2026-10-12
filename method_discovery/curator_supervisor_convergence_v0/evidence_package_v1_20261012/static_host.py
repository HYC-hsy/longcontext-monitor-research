"""Zero-model static host port; no Task process or real provider entry."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009 import adapter
from method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.docker_tool import (
    DockerToolPort, _workspace_class)
from method_discovery.curator_supervisor_convergence_v0.real_task_effect_pilot_preflight_20261010.pilot_analysis_bridge import (
    PilotDockerToolPort, PilotHostBridge)


IMAGE = 'sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1'
KITEX_IMAGE = 'sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e'


class StaticHostPort(PilotDockerToolPort):
    """Same trusted spool/session path, with one certified static /app bind."""

    def __init__(self, fixture: Path, *, image: str = IMAGE):
        if image not in {IMAGE, KITEX_IMAGE}:
            raise RuntimeError('Unregistered static diagnostic image')
        self.fixture = Path(fixture).resolve(strict=True)
        self.app = self.fixture / 'app'
        self.evidence = self.fixture / 'task_evidence'
        self.cognition = self.fixture / 'monitor_private'
        self.private = self.fixture / 'trusted_control'
        self.scratch = self.fixture / 'scratch'
        if not all(path.is_dir() and not path.is_symlink() for path in
                   (self.app, self.evidence, self.cognition)):
            raise RuntimeError('Static cutoff mounts are missing or redirected')
        if self.private.exists() or self.scratch.exists():
            raise RuntimeError('Static host control/scratch path already exists')
        self.private.mkdir()
        self.scratch.mkdir()
        for name in ('home', 'tmp', 'build_cache', 'output'):
            (self.scratch / name).mkdir()
        self.image = image
        inspected = subprocess.run(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'],
                                   text=True, capture_output=True, timeout=20)
        if inspected.returncode or inspected.stdout.strip() != image:
            raise RuntimeError('Pinned static Fyne image identity mismatch')
        self.workspace = _workspace_class()(self.evidence, self.cognition,
                                             task_mounts={'workspace': self.app})
        manifest = json.loads((self.fixture / 'RESEARCH_ONLY_MANIFEST.json').read_text(
            encoding='utf-8'))
        self.historical = manifest['outputs']['historical_completed_outputs']
        self.task_volume = 'static-cutoff:' + manifest['workspace_tree_sha256']
        self.new_sessions = {}
        self._mount_identities = {str(path): self._safe_mount_identity(path)
                                  for path in (self.app, self.evidence, self.cognition,
                                               self.private, self.scratch,
                                               *(self.scratch / name for name in
                                                 ('home', 'tmp', 'build_cache', 'output')))}

    def _docker_args(self, session: str, script: Path, kind: str) -> list[str]:
        self._check_mount_sources()
        interpreter = {'python': '/usr/bin/python3', 'bash': '/bin/bash'}[kind]
        virtual_script = '/pilot_control/' + script.relative_to(self.private).as_posix()
        scratch = self.scratch
        return ['docker', 'run', '--rm', '--name', session, '--network', 'none',
                '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
                '--tmpfs', '/tests:ro,noexec,nosuid,size=1m',
                '--mount', f'type=bind,source={self.app},destination=/app,readonly',
                '--mount', f'type=bind,source={self.private},destination=/pilot_control,readonly',
                '--mount', f'type=bind,source={self.cognition},destination=/logs/agent/monitor/monitor_private,readonly',
                '--mount', f'type=bind,source={self.evidence},destination=/logs/agent/monitor/task_evidence,readonly',
                '--mount', f'type=bind,source={scratch / "home"},destination=/home/monitor',
                '--mount', f'type=bind,source={scratch / "tmp"},destination=/tmp',
                '--mount', f'type=bind,source={scratch / "build_cache"},destination=/cache',
                '--mount', f'type=bind,source={scratch / "output"},destination=/output',
                '--env', 'HOME=/home/monitor', '--env', 'TMPDIR=/tmp',
                '--env', 'GOCACHE=/cache/go', '--env', 'GOPROXY=off',
                '--entrypoint', interpreter, self.image, virtual_script]


def prepare_static(scene: str, destination: Path) -> tuple[dict, StaticHostPort, PilotHostBridge]:
    """Materialize authenticated cutoff and create host-only control queues."""
    manifest = adapter.materialize(scene, destination)
    port = StaticHostPort(destination)
    bridge = PilotHostBridge(root=destination / 'host_spool',
                             run_id='static-' + hashlib.sha256(
                                 str(destination.resolve()).encode()).hexdigest()[:20], port=port)
    return manifest, port, bridge
