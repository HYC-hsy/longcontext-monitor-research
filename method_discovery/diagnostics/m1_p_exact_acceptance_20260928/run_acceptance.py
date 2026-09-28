"""Run the finite exact-M1/P no-model acceptance set.

Every condition executes in a fresh child interpreter.  The child denies
network sockets and replaces only the transport send boundary with scripted
responses.  This is an engineering fixture, not a scientific run.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
POLICY = (ROOT.parent / "rp_candidate_prototypes_20260927" / "P_POLICY.txt").resolve(strict=True)
EXPECTED = "746a695adac4325d6440941d384d543d1364fef9"

def normalize(value):
    return value

def normalized_payload(trace, payload):
    mapping = trace['mechanical_mapping']
    replacements = [(mapping['temp_root'], '<record-local-temp>')]
    replacements += [(path, f'<native-history-archive-{index + 1}>')
                     for index, path in enumerate(mapping['history_archives'])]
    def transform(value):
        if isinstance(value, dict):
            return {key: transform(item) for key, item in value.items()}
        if isinstance(value, list):
            return [transform(item) for item in value]
        if isinstance(value, str):
            # Only explicit, fully recorded mechanical identities are mapped;
            # no arbitrary path substring or evidence/history removal.
            for old, new in replacements:
                value = value.replace(old, new)
            # Production environment-map JSON encodes Windows path strings.
            for old, new in replacements:
                value = value.replace(json.dumps(old)[1:-1], new)
        return value
    return transform(payload)

def run_child(source: Path, mode: str, output: Path) -> None:
    command = [sys.executable, "-I", str(ROOT / "worker.py"), "--source", str(source),
               "--mode", mode, "--output", str(output)]
    if mode == "p":
        command += ["--policy", str(POLICY)]
    subprocess.run(command, cwd=str(ROOT), check=True)

def compare(native: dict, fallback: dict, candidate: dict) -> dict:
    if native["source_identity"]["commit"] != EXPECTED:
        raise AssertionError("native source identity mismatch")
    if fallback["source_identity"]["commit"] != EXPECTED or candidate["source_identity"]["commit"] != EXPECTED:
        raise AssertionError("condition source identity mismatch")
    native_requests = [item["payload"] for item in native["requests"]]
    fallback_requests = [item["payload"] for item in fallback["requests"]]
    candidate_requests = [item["payload"] for item in candidate["requests"]]
    for trace in (native, fallback, candidate):
        if trace['effective_config']['monitor_dcec'] is not True:
            raise AssertionError('DCEC disabled')
        for request in trace['requests']:
            if not request['payload']['system'].startswith(trace['native_system']):
                raise AssertionError('frozen native system replaced')
            expected_tools = [] if request['purpose'] == 'continuation' else trace['provider_tools']
            if request['payload']['tools'] != expected_tools:
                raise AssertionError('provider tools differ from loaded frozen schemas')
    if native_requests != fallback_requests:
        # Temp paths are the only expected mechanical difference across fresh sessions.
        if [normalized_payload(native, x) for x in native_requests] != [normalized_payload(fallback, x) for x in fallback_requests]:
            raise AssertionError("candidate-closed M1 changed the native request/control input")
    if native["controls"] != fallback["controls"]:
        raise AssertionError("candidate-closed M1 changed control results")
    if native["network"] != {"socket_connect_attempts": 0, "requests_attempts": 0}:
        raise AssertionError("native session made an external attempt")
    for result in (fallback, candidate):
        if result["network"] != {"socket_connect_attempts": 0, "requests_attempts": 0}:
            raise AssertionError("condition made an external attempt")
    if len(native_requests) != len(candidate_requests) or len(native_requests) != 9:
        raise AssertionError("unexpected provider-ready request count")
    policy = POLICY.read_text(encoding="utf-8").strip()
    diffs = []
    for index, (base, added) in enumerate(zip(native_requests, candidate_requests)):
        reduced = copy.deepcopy(added)
        if reduced['system'].count('\n\n' + policy) != 1:
            raise AssertionError('P increment is not exactly once')
        reduced['system'] = reduced['system'].replace('\n\n' + policy, '', 1)
        if normalized_payload(native, base) != normalized_payload(candidate, reduced):
            raise AssertionError(f'undeclared request difference at request {index + 1}')
        keys = sorted(set(base) | set(added))
        diffs.append({'request': index + 1,
                      'raw_changed_keys': [key for key in keys if base.get(key) != added.get(key)],
                      'normalized_changed_keys': [key for key in keys if normalized_payload(native, base.get(key)) != normalized_payload(candidate, added.get(key))]})
    for trace in (native, fallback, candidate):
        if trace['remaining_fake_responses'] != 0 or not trace['old_completion_rejected']:
            raise AssertionError('script/control trace incomplete')
        maintenance = [item for item in trace['requests'] if item['purpose'] == 'continuation']
        if len(maintenance) != 1 or maintenance[0]['payload']['tools'] != []:
            raise AssertionError('native continuation tool boundary changed')
        if 'DCEC continuation contract:' not in json.dumps(maintenance):
            raise AssertionError('native DCEC continuation contract missing')
        if not any(item.get('kind') == 'monitor_history_compaction' for item in trace['history_transforms']):
            raise AssertionError('native compaction did not commit')
    for item in candidate["requests"]:
        system = item["payload"]["system"]
        if system.count(policy) != 1:
            raise AssertionError("P policy was lost or duplicated")
        if "R_OVERLAY" in system or "planned P treatment" in system:
            raise AssertionError("research material leaked into P request")
    for item in native["requests"] + fallback["requests"]:
        if policy in item["payload"]["system"]:
            raise AssertionError("P policy remained in M1")
    return {
        "native_equals_candidate_closed_m1": True,
        "m1_provider_ready_requests": len(native_requests),
        "p_provider_ready_requests": len(candidate_requests),
        "p_policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest(),
        "p_system_occurs_once_each_request": True,
        "actual_external_requests": sum(sum(trace['network'].values()) for trace in (native, fallback, candidate)),
        "actual_model_calls": sum(trace['network']['requests_attempts'] for trace in (native, fallback, candidate)),
        "request_differences": diffs,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output_root.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output root must be absent/empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    paths = {mode: output / f"{mode}.json" for mode in ("native", "fallback", "p")}
    run_child(source, "native", paths["native"])
    run_child(source, "fallback", paths["fallback"])
    run_child(source, "p", paths["p"])
    run_child(source, "fallback", output / 'clean_m1_after_p.json')
    native, fallback, candidate = [json.loads(paths[key].read_text(encoding="utf-8"))
                                   for key in ("native", "fallback", "p")]
    summary = compare(native, fallback, candidate)
    clean = json.loads((output / 'clean_m1_after_p.json').read_text(encoding='utf-8'))
    compare(native, clean, candidate)
    summary['clean_m1_after_p_matches_native'] = True
    summary['captured_provider_ready_requests_total'] = sum(len(trace['requests']) for trace in (native, fallback, candidate, clean))
    negative_results = []
    mutations = {
        'dcec_config_disabled': lambda x: x['effective_config'].update(monitor_dcec=False),
        'tool_deleted': lambda x: x['requests'][0]['payload']['tools'].pop(),
        'schema_changed': lambda x: x['requests'][0]['payload']['tools'][0]['input_schema'].update(required=[]),
        'research_field_added': lambda x: x['requests'][0]['payload'].update(research_metadata={'expected': 'approve'}),
        'base_system_replaced': lambda x: x['requests'][0]['payload'].update(system='approximate supervisor'),
        'active_view_removed': lambda x: x['requests'][0]['payload']['messages'].pop(),
        'p_duplicated': lambda x: x['requests'][0]['payload'].update(system=x['requests'][0]['payload']['system'] + '\n\n' + POLICY.read_text(encoding='utf-8').strip()),
        'r_stacked': lambda x: x['requests'][0]['payload'].update(system=x['requests'][0]['payload']['system'] + '\n\n' + (POLICY.parent / 'R_POLICY.txt').read_text(encoding='utf-8').strip()),
        'wrong_source_identity': lambda x: x['source_identity'].update(commit='current-branch'),
    }
    for name, mutation in mutations.items():
        bad = copy.deepcopy(candidate)
        mutation(bad)
        try:
            compare(native, fallback, bad)
        except (AssertionError, KeyError):
            negative_results.append({'case': name, 'result': 'rejected'})
        else:
            raise AssertionError('counterexample escaped: ' + name)
    polluted = copy.deepcopy(fallback)
    polluted['requests'][0]['payload']['system'] += '\n\n' + POLICY.read_text(encoding='utf-8').strip()
    try:
        compare(native, polluted, candidate)
    except AssertionError:
        negative_results.append({'case': 'candidate_off_residue', 'result': 'rejected'})
    else:
        raise AssertionError('candidate-off residue escaped')
    command = [sys.executable, '-I', str(ROOT / 'worker.py'), '--source', str(ROOT.parents[2]),
               '--mode', 'native', '--output', str(output / 'must_not_exist.json')]
    bad_source = subprocess.run(command, capture_output=True, text=True)
    if bad_source.returncode == 0 or 'source commit is not frozen M1' not in bad_source.stderr:
        raise AssertionError('current checkout was not rejected')
    (output / 'wrong_source_failure.txt').write_text(bad_source.stderr, encoding='utf-8')
    command[command.index('--source') + 1] = str(source)
    command[command.index('--mode') + 1] = 'off'
    disabled = subprocess.run(command, capture_output=True, text=True)
    if disabled.returncode == 0 or 'native DCEC-v1 was not enabled' not in disabled.stderr:
        raise AssertionError('disabled DCEC was not rejected')
    (output / 'disabled_dcec_failure.txt').write_text(disabled.stderr, encoding='utf-8')
    negative_results += [{'case': 'actual_current_checkout_import', 'result': 'rejected_before_import'},
                         {'case': 'actual_dcec_disabled', 'result': 'rejected_before_transport'}]
    summary['negative_tests'] = negative_results
    summary.update({"source": str(source), "source_commit": EXPECTED,
                    "m1_anchor": EXPECTED, "conditions": ["native_m1", "candidate_closed_m1", "m1_plus_p"],
                    "old_c6e2_prototype_not_reused_as_exact_baseline": True,
                    "engineering_fixture_not_scientific_record": True})
    (output / "acceptance_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {file.name: {'sha256': hashlib.sha256(file.read_bytes()).hexdigest(), 'bytes': file.stat().st_size}
                for file in sorted(output.iterdir()) if file.is_file()}
    (output / 'file_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
