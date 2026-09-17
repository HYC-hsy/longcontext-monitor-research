"""Allowlisted, local-only research snapshot. Never uploads or reads credentials."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'research_collaboration_private'
records = []
PATTERNS = [
    (r'\bsk-[A-Za-z0-9_-]{16,}', '[REDACTED_API_KEY]'),
    (r'(?i)(Bearer\s+)[A-Za-z0-9_.-]{16,}', r'\1[REDACTED_TOKEN]'),
    (r'(?i)C:[\\/]+Users[\\/]+[^\\/\s"<>]+', 'C:/Users/REDACTED'),
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sanitize(text):
    for pattern, replacement in PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def export(source, target, transform=None):
    raw = source.read_bytes()
    text = raw.decode('utf-8-sig')
    if transform:
        text = transform(text)
    text = sanitize(text)
    dest = OUT / target
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding='utf-8')
    records.append(dict(source=str(source.relative_to(ROOT)).replace('\\', '/'),
                        target=str(target), source_sha256=digest(raw),
                        exported_sha256=digest(dest.read_bytes()),
                        transformation='filtered JSONL + redaction' if transform else 'UTF8 + redaction',
                        bytes=dest.stat().st_size))


def public_cycle_result(result):
    """Do not publish author result prompt/response copies or future fields.

    Decisions and tool observations are exported separately. Digests allow a
    reviewer with local access to identify the omitted originals.
    """
    allowed = {'operations', 'should_inject', 'context_for_action'}
    public = {key: value for key, value in result.items() if key in allowed}
    public['omitted_fields'] = {
        key: {'sha256': digest(json.dumps(value, ensure_ascii=False,
                                        sort_keys=True).encode('utf-8'))}
        for key, value in result.items() if key not in allowed
    }
    return public


def dialogue(text):
    keep = {'tool_call', 'tool_result', 'model_output', 'pma_fused_phase_started',
            'pma_direct_intervention', 'pma_bank_operation', 'pma_fused_cycle',
            'pma_control_intent_handoff', 'pma_control_intent_received', 'control_result'}
    result = []
    for line, value in enumerate(text.splitlines(), 1):
        event = json.loads(value)
        if event.get('event') in keep:
            if event['event'] == 'pma_fused_cycle':
                event['result'] = public_cycle_result(event['result'])
            data = event.get('data')
            if (event.get('event') == 'tool_result' and isinstance(data, dict)
                    and str(data.get('path', '')).endswith('original_task.txt')):
                data['content'] = '[Original benchmark task text omitted; see research summary.]'
                data['export_redaction'] = 'Original task body withheld; source metadata retained.'
            event['source_line'] = line
            result.append(json.dumps(event, ensure_ascii=False))
    return '\n'.join(result) + '\n'


def task_commands(text):
    rows = []
    for line, value in enumerate(text.splitlines(), 1):
        event = json.loads(value)
        if event.get('boundary') != 'post_model_pre_tool':
            continue
        rows.append(json.dumps({'source_line': line, 'task_turn': event.get('task_turn'),
            'synopsis': event.get('synopsis'),
            'tool_names': [c.get('name') for c in event.get('tool_calls', [])],
            'code_calls': [c for c in event.get('tool_calls', []) if c.get('name') == 'code_run']},
            ensure_ascii=False))
    return '\n'.join(rows) + '\n'


def main():
    core = ROOT / 'GenericAgent-main/monitor_agent_core'
    for source in sorted(core.rglob('*')):
        if not source.is_file() or '__pycache__' in source.parts:
            continue
        if source.suffix not in {'.py', '.md', '.toml'} and 'LICENSE' not in source.name:
            continue
        export(source, 'src/monitor_agent_core/' + source.relative_to(core).as_posix())
    for name in ['test_monitor_pma_fused.py', 'test_monitor_pma_memory.py',
                 'test_monitor_agent_workspace.py', 'test_monitor_follow_wait.py']:
        export(ROOT / 'GenericAgent-main/tests' / name, 'tests/' + name)
    export(ROOT / 'GenericAgent-main/ga_monitor_adapter.py', 'adapters/ga_monitor_adapter.py')
    export(ROOT / 'GenericAgent-main/LICENSE', 'third_party/GENERICAGENT_LICENSE')
    fyne = ROOT / 'long_context_bench/.cache/m12_roadmap_tasks/fyn-2.2.0-roadmap/environment/repo'
    for name in ['LICENSE', 'AUTHORS']:
        if (fyne / name).exists():
            export(fyne / name, 'third_party/FYNE_' + name)
    docs = [
        'PMA_FUSED_R8_TRAJECTORY_AUDIT_20260914.md',
        'R6_PMA_MANUAL_COMPARATIVE_AUDIT_20260913.md',
        'PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md',
        'METHOD_DISCOVERY_HYPOTHESIS_DRIVEN_PLAN_20260906.md',
        'PMA_FUSED_R7_OUTPUT_AUDIT_AND_REPAIR_20260914.md',
        'PMA_R8_COMPACTION_TEMPORAL_AUDIT_20260917.md',
        'PMA_PHASE_HANDOFF_REPAIR_20260917.md',
        'PMA_PHASE_HANDOFF_R9_AUDIT_20260917.md',
    ]
    for name in docs:
        export(ROOT / 'method_discovery/docs' / name, 'docs/archive/' + name)
    jobs = ROOT / 'long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs'
    r8 = jobs / 'clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r8/fyn-2.2.0-roadmap__FrLR3d6'
    private = r8 / 'agent/monitor/monitor_private'
    for name in ['reviews.jsonl', 'continuations.jsonl', 'provider_usage.jsonl']:
        export(private / 'audit' / name, 'evidence/automatic_fyne_r8/' + name)
    export(private / 'audit/dialogue.jsonl', 'evidence/automatic_fyne_r8/decisions.jsonl', dialogue)
    export(private / 'pma_memory.json', 'evidence/automatic_fyne_r8/final_memory.json')
    r9 = jobs / 'clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r9/fyn-2.2.0-roadmap__8hwmEC4'
    private9 = r9 / 'agent/monitor/monitor_private'
    for name in ['reviews.jsonl', 'continuations.jsonl', 'provider_usage.jsonl', 'history_transforms.jsonl']:
        export(private9 / 'audit' / name, 'evidence/automatic_fyne_r9/' + name)
    export(private9 / 'audit/dialogue.jsonl', 'evidence/automatic_fyne_r9/decisions.jsonl', dialogue)
    export(private9 / 'pma_memory.json', 'evidence/automatic_fyne_r9/final_memory.json')
    export(private9 / 'delivery_feedback.jsonl', 'evidence/automatic_fyne_r9/delivery_feedback.jsonl')
    export(r9 / 'verifier/reward.json', 'evidence/automatic_fyne_r9/reward.json')
    export(r9 / 'agent/monitor/task_evidence/public_events.jsonl',
           'evidence/automatic_fyne_r9/task_commands.jsonl', task_commands)
    manual = jobs / 'clean-monitor-fyn-2.2.0-roadmap-phase1-manual-20260907-r1/fyn-2.2.0-roadmap__Fk7n6ZM/agent/manual_completion/interventions/archive'
    for source in sorted(manual.glob('*.txt')):
        export(source, 'evidence/manual_fyne_reference/' + source.name)
    (OUT / 'evidence/manifest.json').write_text(json.dumps({
        'source_head': subprocess.check_output(
            ['git', '-c', 'safe.directory=' + ROOT.as_posix(), 'rev-parse', 'HEAD'],
            cwd=ROOT, text=True).strip(),
        'r8_code_commit': '2a2cc9e', 'r9_code_commit': '46ba27f',
        'status': 'Private research review snapshot; filtered evidence, not full replay',
        'excluded': ['credentials', 'Git history', 'private assistant sessions',
                     'hidden tests', 'benchmark source bundles', 'full repeated model inputs'],
        'files': records}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(records), 'bytes': sum(r['bytes'] for r in records)}))


if __name__ == '__main__':
    main()
