"""Verify portable, redacted A/B Harbor fixture evidence for generic V4 runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from .prepare_six_task_manifest import V3_SOURCE_FILES, _committed_source_sha


HARBOR_COMMIT = '459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc'
VENDOR_FILES = (
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'vendor/pma_89e5c0d/src/memory_agent/memory/memory_agent.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'vendor/pma_89e5c0d/src/memory_agent/memory/universal_memory.py',
)
SOURCE_FILES = tuple(dict.fromkeys(V3_SOURCE_FILES + (
    'experiment_runner/__main__.py',
    'experiment_runner/evaluation_cache.py',
    'experiment_runner/runtime_reuse.py',
    'GenericAgent-main/research_runtime.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'archive_live_six_task.py',
    'method_discovery/curator_supervisor_convergence_v0/'
    'real_task_effect_pilot_preflight_20261010/pilot_fake_gateway.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'control_processes.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'single_run.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'run_selection.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'single_run_fixture.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'single_run_certification.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'collect_single_run_fixture.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'harbor_adapter.py',
)))
CANDIDATE_SOURCE_FILES = SOURCE_FILES + (
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'episode.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'decision_reminder_agent.py',
)
GAP_SOURCE_FILES = SOURCE_FILES + (
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'episode.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'gap_memory_agent.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'gap_store.py',
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    'gap_prompts.py',
)
EVIDENCE_GAP_SOURCE_FILES = GAP_SOURCE_FILES + tuple(
    'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/'
    + name for name in ('gap_evidence.py', 'evidence_gap_store.py', 'evidence_gap_agent.py',
                         'evidence_gap_context.py', 'source_memory.py', 'evidence_requirements.txt',
                         'aligned_evidence_gap_agent.py', 'aligned_evidence_gap_store.py',
                         'gap_evidence_alignment.py',
                         'latest_evidence_gap_agent.py', 'latest_evidence_gap_store.py',
                         'graded_evidence_alignment.py', 'vendor/langextract_3a68580/fuzzy.py',
                         'fuzzy_candidate_windows.py', 'vendor/langextract_3a68580/chunking.py',
                         'vendor/langextract_3a68580/__init__.py',
                         'vendor/langextract_3a68580/alignment.py',
                         'vendor/langextract_3a68580/tokenizer.py',
                         'vendor/langextract_3a68580/requirements.txt')
)
EVIDENCE_FILES = (
    'execution_identity.json',
    'live_result.json', 'agent_start_identity.json', 'agent_end_native.json',
    'writer_termination_check.json', 'control_process_registry.json',
    'native_reports_checked.json', 'native_test_execution.json',
    'synthetic_test.sh', 'research_events.jsonl',
    'memory_payload.jsonl', 'fake_authorization_removed.json',
)


def _committed_evidence_sha(checkout: Path, path: Path) -> str:
    relative = path.resolve(strict=True).relative_to(checkout.resolve(strict=True)).as_posix()
    if subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', relative],
                      cwd=checkout).returncode:
        raise RuntimeError(f'fixture evidence differs from committed blob: {relative}')
    blob = subprocess.run(['git', 'show', f'HEAD:{relative}'], cwd=checkout,
                          capture_output=True, check=True).stdout
    digest = hashlib.sha256(blob).hexdigest()
    if digest != hashlib.sha256(path.read_bytes()).hexdigest():
        raise RuntimeError(f'fixture evidence bytes differ from Git blob: {relative}')
    return digest


def require_bound_gap_memory(path: Path) -> None:
    """Validate final bank links using its canonical loader, not a reminder proxy."""
    stage = Path(__file__).resolve().parent
    original_path = sys.path[:]
    try:
        sys.path[:0] = [str(stage), str(stage / 'vendor/pma_89e5c0d/src')]
        from aligned_evidence_gap_store import AlignedEvidenceGapMemory
        from latest_evidence_gap_store import LatestEvidenceGapMemory
        modules = {name: stage / (name + '.py') for name in (
            'aligned_evidence_gap_store', 'latest_evidence_gap_store',
            'evidence_gap_store', 'gap_evidence', 'gap_store', 'source_memory')}
        modules['memory_agent.memory.universal_memory'] = (
            stage / 'vendor/pma_89e5c0d/src/memory_agent/memory/universal_memory.py')
        if any(Path(sys.modules[name].__file__).resolve() != expected.resolve()
               for name, expected in modules.items()):
            raise RuntimeError('evidence fixture validator loaded foreign source')
        value = json.loads(path.read_text(encoding='utf-8'))
        policy = value.get('gap_alignment_policy')
        loader = (LatestEvidenceGapMemory if policy == LatestEvidenceGapMemory.policy
                  else AlignedEvidenceGapMemory)
        memory = loader.from_dict(value)
    finally:
        sys.path[:] = original_path
    for gap in memory.entries:
        revision = memory.revisions.get(memory.active_revisions.get(gap.id))
        if revision is None or revision.receipt_id is None:
            continue
        receipt = memory.receipts[revision.receipt_id]
        if receipt.bound_refs:
            return
    raise RuntimeError('evidence gap fixture has no committed bound gap')


def verify_evidence(evidence: Path, *, require_committed: bool = True,
                    research_candidate: str | None = None,
                    conditions: tuple[str, ...] = ('A', 'B'), citation_review_gate=None,
                    citation_review_strategy=None) -> dict:
    if conditions not in (('A',), ('A', 'B')) or (conditions == ('A',) and
            research_candidate is not None):
        raise ValueError('unsupported single-run certification conditions')
    from .citation_gate_config import validate_gate,validate_strategy
    validate_gate(citation_review_gate,research_candidate)
    validate_strategy(citation_review_gate,citation_review_strategy)
    if citation_review_gate and conditions != ('A','B'):raise ValueError('gate requires A/B native evidence')
    gate_certificate=None
    checkout = Path(__file__).resolve().parents[3]
    outcomes = {}
    hashes = {}
    for condition in conditions:
        current = source_identity(checkout,
            candidate=research_candidate is not None and condition == 'B',
            gap=research_candidate == 'pma_gap_memory_v0' and condition == 'B',
            evidence_gap=research_candidate == 'pma_gap_evidence_v1' and condition == 'B')
        base = evidence / condition
        required = [name for name in EVIDENCE_FILES
                    if condition == 'B' or name != 'memory_payload.jsonl']
        for name in required:
            path = base / name
            if not path.is_file():
                raise RuntimeError(f'generic {condition} evidence missing: {name}')
            hashes[f'{condition}/{name}'] = (_committed_evidence_sha(checkout, path)
                if require_committed else hashlib.sha256(path.read_bytes()).hexdigest())
        load = lambda name: json.loads((base / name).read_text(encoding='utf-8'))
        result, started, ended = (load(name) for name in
            ('live_result.json', 'agent_start_identity.json', 'agent_end_native.json'))
        writers, registry, reports = (load(name) for name in
            ('writer_termination_check.json', 'control_process_registry.json',
             'native_reports_checked.json'))
        removed = load('fake_authorization_removed.json')
        executed = load('execution_identity.json')
        if (executed.get('source_files') != current or
                executed.get('vendor_files') != vendor_identity(checkout) or
                executed.get('pma_vendor_commit') !=
                '89e5c0d6aadfe531a1aee42fd290d48be89973dd' or
                executed.get('harbor_commit') != HARBOR_COMMIT):
            raise RuntimeError(f'generic {condition} fixture execution identity differs')
        execution = load('native_test_execution.json')
        synthetic_script = (base / 'synthetic_test.sh').read_bytes()
        expected_candidate = research_candidate if condition == 'B' else 'U'
        if (research_candidate is not None and
                result.get('research_candidate') != expected_candidate):
            raise RuntimeError('candidate fixture ran a different strategy')
        if (result.get('condition') != condition or
                result.get('zero_model_fixture_only') is not True or
                result.get('harbor_return_code') != 0 or
                result.get('cleanup_confirmed') is not True or
                result.get('fake_provider_captures', 0) < 2 or
                result.get('native_result', {}).get('status') != 'native_recorded' or
                result.get('native_reports_checked') is not True or
                ended.get('control_processes_stopped') is not True or
                ended.get('gateway_stopped') is not True or
                writers.get('control_remaining') != [] or
                not any(row.get('kind') == 'transport' for row in
                        writers.get('registered_control_processes', [])) or
                registry.get('container_id') != started.get('container_id') or
                started.get('provider_key_env_absent') is not True or
                started.get('hidden_tests_absent') is not True or
                reports.get('all_reports_executed') is not True or
                execution.get('observed') is not True or
                b'http://127.0.0.1:19173' not in synthetic_script or
                removed.get('authorization_removed') is not True):
            raise RuntimeError(f'generic {condition} fixture incomplete')
        events = [json.loads(line) for line in (base / 'research_events.jsonl').read_text(
            encoding='utf-8').splitlines()]
        ready = [row for row in events if row.get('event_type') == 'provider_request_ready']
        attempts = [row for row in events if row.get('event_type') == 'provider_request_attempt']
        if (len(ready) < 2 or len(attempts) < 2 or
                not all(row.get('payload', {}).get('content_availability') == 'complete'
                        for row in ready)):
            raise RuntimeError(f'generic {condition} Task requests not captured')
        if condition == 'B':
            if (result.get('worker_return_code') != 0 or
                    not any(row.get('event_type') == 'pma_reminder_appended'
                            for row in events) or
                    not any(row.get('payload', {}).get('pma_reminder_event_id')
                            for row in ready)):
                raise RuntimeError('generic PMA reminder did not enter Task request')
            phases = [json.loads(line).get('phase') for line in
                      (base / 'memory_payload.jsonl').read_text(encoding='utf-8').splitlines()]
            required_phases = ({'maintenance', 'selection'}
                if research_candidate in ('pma_gap_memory_v0', 'pma_gap_evidence_v1') else
                {'bank_management', 'context_decision'})
            if not required_phases <= set(phases):
                raise RuntimeError('generic PMA two-stage transport absent')
            if research_candidate in ('pma_gap_memory_v0','pma_gap_evidence_v1'):
                require_gap_phases(phases,citation_review_gate)
            if research_candidate in ('pma_gap_memory_v0', 'pma_gap_evidence_v1') and not (
                    base / 'gap_cycle.jsonl').is_file():
                raise RuntimeError('gap candidate cycle evidence absent')
            if research_candidate == 'pma_gap_evidence_v1':
                cycles = [json.loads(line) for line in
                          (base / 'gap_cycle.jsonl').read_text(encoding='utf-8').splitlines()]
                if not any(row.get('evidence_report', {}).get('accepted') is True
                           for row in cycles):
                    raise RuntimeError('evidence gap fixture has no accepted evidence batch')
                require_bound_gap_memory(base / 'memory.json')
                if citation_review_gate:
                    from .gate_certification import verify_certificate
                    gate_certificate=verify_certificate(base,citation_review_gate,citation_review_strategy)
                elif executed.get('gate_config'):
                    raise RuntimeError('gate evidence cannot certify baseline')
        else:
            if any(row.get('event_type') == 'pma_reminder_appended' for row in events):
                raise RuntimeError('generic Task-only fixture used PMA')
        outcomes[condition] = {'run_id': result['run_id'],
                               'task': result['task'],
                               'requests': len(ready), 'attempts': len(attempts),
                               'control_stopped': True, 'native_recorded': True}
    for path in sorted(evidence.rglob('*')):
        if not path.is_file() or path.name == 'FILE_HASHES.json':
            continue
        name = path.relative_to(evidence).as_posix()
        if name not in hashes:
            hashes[name] = (_committed_evidence_sha(checkout, path)
                if require_committed else hashlib.sha256(path.read_bytes()).hexdigest())
    return {'outcomes': outcomes, 'file_sha256': hashes,
            **({'gate_certificate':gate_certificate} if citation_review_gate else {})}


def source_identity(checkout: Path, *, candidate: bool = False,
                    gap: bool = False, evidence_gap: bool = False) -> dict:
    files = (EVIDENCE_GAP_SOURCE_FILES if evidence_gap else GAP_SOURCE_FILES if gap else
             CANDIDATE_SOURCE_FILES if candidate else SOURCE_FILES)
    return {name: _committed_source_sha(checkout, name) for name in files}


def vendor_identity(checkout: Path) -> dict:
    return {name: _committed_source_sha(checkout, name) for name in VENDOR_FILES}


def require_gap_phases(phases,mode=None):
    if mode is None:
        if set(phases)!={'maintenance','selection'}:
            raise RuntimeError('gap candidate made a non-two-stage transport call')
    else:
        from .citation_gate_config import MODES
        allowed={'maintenance','selection','citation_review'}|({'citation_repair'} if mode=='gate-one-repair' else set())
        if mode not in MODES or set(phases)!=allowed:
            raise RuntimeError('gate fixture phase contract differs')
        # This is only a preliminary check. verify_certificate below is mandatory.
