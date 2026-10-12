"""Native Go JSON checks through the already isolated Docker tool port."""

import hashlib

import pytest

from .go_checks import classify_go_test
from .static_host import IMAGE, KITEX_IMAGE, StaticHostPort, adapter


def test_fault_injected_go_timeout_and_incomplete_output_remain_unknown():
    assert classify_go_test(b'{"Action":"run","Test":"TestX"}', exit_code=0,
                            reason=None, requested_test='TestX')['classification'] == 'output_incomplete'
    assert classify_go_test(b'', exit_code=None, reason='timeout',
                            requested_test='TestX')['classification'] == 'timeout'
    assert classify_go_test(b'PASS\n', exit_code=0, reason=None,
                            requested_test='TestX')['behavior_verified'] is False


def _run(port, command):
    result = port.execute('code_run', {'code': command, 'type': 'bash',
                                       'timeout': 120, 'wait_seconds': 5})
    for _ in range(30):
        if result['status'] != 'running' and not result['next_read']:
            break
        result = port.execute('code_run', {'session_id': result['session_id'],
                                           'wait_seconds': 5})
    assert result['status'] != 'running', result
    output = (port.private / 'audit' / 'commands' / result['session_id'] /
              'output.log').read_bytes()
    return result, output


@pytest.mark.parametrize('image,label', [(IMAGE, 'Fyne'), (KITEX_IMAGE, 'Kitex')])
def test_native_go_execution_classifications(tmp_path, image, label):
    fixture = tmp_path / 'cutoff'
    adapter.materialize('C02', fixture)
    port = StaticHostPort(fixture, image=image)
    try:
        identity, output = _run(port, 'go version\ncommand -v go\nsha256sum "$(command -v go)"\n')
        assert identity['status'] == 'success', output.decode(errors='replace')
        toolchain = output.decode('utf-8')
        assert 'go version' in toolchain and len(toolchain.splitlines()) >= 3
        setup = (
            'mkdir -p /tmp/go_check\ncd /tmp/go_check\n'
            "printf '%s\\n' 'module offlinecheck' '' 'go 1.18' >go.mod\n"
            "printf '%s\\n' 'package check' 'import \"testing\"' "
            "'func TestPass(t *testing.T) {}' "
            "'func TestFail(t *testing.T) { t.Fatal(\"expected failure\") }' "
            "'func TestSkip(t *testing.T) { t.Skip(\"expected skip\") }' >check_test.go\n"
        )
        cases = [('pass', 'TestPass', 'test_passed'),
                 ('fail', 'TestFail', 'test_failed'),
                 ('skip', 'TestSkip', 'all_skipped'),
                 ('zero', 'TestDoesNotExist', 'zero_matching_tests')]
        results = {}
        for name, selector, expected in cases:
            command = (setup if name == 'pass' else 'cd /tmp/go_check\n') + (
                f"go test -json -count=1 -run '^{selector}$' .\n")
            process, raw = _run(port, command)
            classification = classify_go_test(raw, exit_code=process['exit_code'],
                                               reason=process['reason'],
                                               requested_test=selector)
            assert classification['classification'] == expected, (name, classification, raw)
            results[name] = classification
        compile_command = (
            'mkdir -p /tmp/go_check_bad\ncd /tmp/go_check_bad\n'
            "printf '%s\\n' 'module offlinebad' '' 'go 1.18' >go.mod\n"
            "printf '%s\\n' 'package bad' 'func broken(' >bad.go\n"
            'go test -json -count=1 .\n'
        )
        process, raw = _run(port, compile_command)
        compile_result = classify_go_test(raw, exit_code=process['exit_code'],
                                          reason=process['reason'], requested_test=None)
        print({'image': label, 'compile_raw': raw.decode('utf-8', errors='replace')})
        assert compile_result['classification'] == 'build_or_environment_failure'
        assert not compile_result['behavior_verified']
        assert results['pass']['behavior_verified']
        assert not any(results[name]['behavior_verified'] for name in ('fail', 'skip', 'zero'))
        print({'image': label, 'image_id': image, 'go_identity': toolchain.strip(),
               'classifications': {key: value['classification'] for key, value in results.items()},
               'compile': compile_result['classification'],
               'raw_output_sha256': hashlib.sha256(raw).hexdigest()})
    finally:
        port.close()
