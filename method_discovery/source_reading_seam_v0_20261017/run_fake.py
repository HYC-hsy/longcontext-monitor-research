"""env -i /usr/bin/python3 -I -S run_fake.py > results.json 2> results.stderr

Adapted from the already reviewed reference_revision_v0/run_fake.py boundary.
No Task commands, provider, credential reader, or downloaded new code executes.
"""
import asyncio
import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
from types import ModuleType

ROOT = Path(__file__).resolve().parent
TRUSTED = Path('/workspace/shared/deep_supervisor_20261017/lab/integration/run_actual_pma.py')
TRUSTED_SHA = '856f00548f4e497eabf27a4783cd18820ace9441110298c7895043304db8f948'
AUDIT = Path('/workspace/shared/input_views54_audit_20261017/integrity')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    if (not sys.flags.isolated or not sys.flags.no_site or
            any(k != 'LC_CTYPE' or v != 'C.UTF-8' for k, v in os.environ.items())):
        raise RuntimeError('strict fake mode requires env -i and python -I -S')
    sys.dont_write_bytecode = True
    if hashlib.sha256(TRUSTED.read_bytes()).hexdigest() != TRUSTED_SHA:
        raise RuntimeError('reviewed local harness changed')
    reuse = json.loads((ROOT / 'reuse_manifest.json').read_text())
    for name, row in reuse.items():
        original = ROOT / name if not name.startswith('/') else Path(name)
        if hashlib.sha256(original.read_bytes()).hexdigest() != row['sha256']:
            raise RuntimeError('reused source changed: ' + name)
        if 'copy' in row and (ROOT / row['copy']).read_bytes() != original.read_bytes():
            raise RuntimeError('reuse copy differs: ' + name)
    ref = load('reviewed_pma_reference', TRUSTED)
    base = load('reference_adapter', ROOT / 'reference_adapter.py')
    evidence = load('reference_evidence', ROOT / 'reference_evidence.py')
    projection = load('input_views', ROOT / 'input_views.py')
    adapter = load('source_reading_adapter', ROOT / 'adapter.py')
    checks = load('source_reading_checks', ROOT / 'checks.py')
    cases, archive_hash = evidence.load_cases(base.FrozenInputs)
    # Read archived packets as data, not their launch scripts. Compare the exact
    # retained projector against all six original F/EB views before seam tests.
    manifest = json.loads((AUDIT / 'public_run/manifest_public.json').read_text())
    rows = manifest['planned_order']
    pairs = []
    for n in range(0, len(rows), 9):
        pair = []
        for offset in (0, 1):
            row = rows[n + offset]
            path = AUDIT / 'public_run' / f"{n + offset + 1:02}-{row['run_id']}" / 'request.json'
            packet = json.loads(path.read_text())
            if hashlib.sha256(packet['prompt'].encode()).hexdigest() != row['request_prompt_sha256']:
                raise RuntimeError('archived projection request hash mismatch')
            pair.append(packet)
        pairs.append(pair)
    violations = []
    with tempfile.TemporaryDirectory(prefix='source_reading_seam_fake_') as temp:
        stage = Path(temp)
        for relative, expected in ref.PINS.items():
            data = (ref.SOURCE / relative).read_bytes()
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError('pinned source mismatch: ' + relative)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        for name, path in [('memory_agent', stage / 'src/memory_agent'),
                           ('memory_agent.memory', stage / 'src/memory_agent/memory')]:
            shell = ModuleType(name)
            shell.__path__ = [str(path)]
            sys.modules[name] = shell
        shim = ModuleType('shortuuid')
        counter = iter(range(1, 100000))
        shim.uuid = lambda: f'{next(counter):08d}'
        shim.__fixture_only__ = True
        sys.modules['shortuuid'] = shim
        stdlib = Path(os.__file__).resolve().parent
        readable_authored = {ROOT / name for name in (
            'adapter.py', 'checks.py', 'run_fake.py', 'input_views.py',
            'reference_adapter.py', 'reference_evidence.py')}

        def audit(event, args):
            blocked = event in {
                'socket.connect', 'socket.bind', 'socket.getaddrinfo',
                'socket.sendto', 'socket.sendmsg', 'subprocess.Popen', 'os.system',
                'os.exec', 'os.posix_spawn', 'os.fork', 'os.putenv', 'os.unsetenv'}
            if event == 'import':
                blocked = (args[0].split('.')[0] not in sys.stdlib_module_names and
                           args[0].split('.')[0] not in {'memory_agent', 'shortuuid'})
            if event == 'socket.__new__':
                blocked = args[1] != socket.AF_UNIX
            if event == 'open':
                path, mode, flags = args
                writes = ((isinstance(mode, str) and any(c in mode for c in 'wax+')) or
                          (isinstance(flags, int) and bool(flags & (
                              os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))))
                allowed = False
                if isinstance(path, (str, bytes)):
                    resolved = Path(os.fsdecode(path)).resolve()
                    allowed = (resolved.is_relative_to(stage) or
                               resolved.is_relative_to(stdlib) or
                               resolved in readable_authored or resolved == TRUSTED)
                blocked = writes or not allowed
            if blocked:
                violations.append(dict(event=event, args=str(args)))
                raise PermissionError('offline boundary: ' + event)

        sys.addaudithook(audit)
        module = importlib.import_module('memory_agent.memory.memory_agent')
        assert Path(module.__file__).resolve() == (stage / 'src/memory_agent/memory/memory_agent.py').resolve()
        logging.disable(logging.CRITICAL)
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            report = asyncio.run(checks.run_checks(module, adapter, projection, cases, pairs))
        assert not violations, violations
        assert not any(m.split('.')[0] in {'openai', 'anthropic', 'litellm', 'requests', 'httpx', 'pydantic'} for m in sys.modules)
        print(json.dumps(dict(
            status='mechanical_checks_passed', real_model_calls=0,
            semantic_quality='not_tested', task_continuation='not_run',
            integration='original_two_phase_PMA_plus_offline_source_reading_seam_only',
            source_revision='89e5c0d6aadfe531a1aee42fd290d48be89973dd',
            source_hashes=ref.PINS, reviewed_harness_sha256=TRUSTED_SHA,
            archive_sha256=archive_hash, archive_entries_verified=42,
            reused_sources=reuse, blocked_events=violations,
            captured_vendor_logs=captured.getvalue(), **report), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
