"""No model calls or benchmark execution: verify the network-less socket route."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

from scripts.isolated_run_bundle import build_bundle


def run_check(output, runtime):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'fixture-source'
    source.mkdir()
    (source / 'agentmain.py').write_text('# Not a task Agent\n', encoding='utf-8')
    (source / 'mykey.py').write_text(
        "task={'model':'claude-fixture','apikey':'not-a-key','apibase':'https://example.invalid'}\n"
        "monitor={'model':'fixture','apikey':'not-a-key','apibase':'https://example.invalid'}\n",
        encoding='utf-8')
    home = next((Path(runtime) / 'python').glob('cpython-3.12.*-linux-x86_64-gnu')).name
    python = f'/opt/m4-runtime/python/{home}/bin/python3.12'
    copied, compose_path = build_bundle(output / 'bundle', source, runtime, home,
                                         'task', 'monitor', 15340)
    config_path = output / 'bundle/gateway/config.json'
    config = json.loads(config_path.read_text())
    config['telemetry'] = 'http://127.0.0.1:19000/v1/traces'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    fake = (
        "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
        "class H(BaseHTTPRequestHandler):\n"
        " def do_POST(self):\n"
        "  self.rfile.read(int(self.headers['Content-Length']))\n"
        "  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()\n"
        "  self.wfile.write(b'data: first\\n\\n');self.wfile.flush()\n"
        "  self.wfile.write(b'data: last\\n\\n');self.wfile.flush()\n"
        "HTTPServer(('127.0.0.1',19000),H).serve_forever()\n")
    (output / 'bundle/gateway/fake.py').write_text(fake, encoding='utf-8')
    compose = json.loads(compose_path.read_text())
    compose['services']['main'].update(image='debian:bookworm-slim',
        command=['sleep', 'infinity'])
    compose['services']['main']['volumes'] += [
        f'{Path(runtime).resolve().as_posix()}:/opt/m4-runtime:ro',
        f'{copied.as_posix()}:/source:ro']
    compose_path.write_text(json.dumps(compose), encoding='utf-8')
    project = 'isolation-check-' + uuid.uuid4().hex[:10]
    prefix = ['docker', 'compose', '-p', project, '-f', str(compose_path)]
    report = {'project': project, 'api_calls': 0, 'real_task_started': False}

    def command(args, timeout=60):
        result = subprocess.run(prefix + args, capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=timeout)
        if result.returncode:
            raise RuntimeError((result.stderr or result.stdout)[-4000:])
        return result.stdout

    try:
        command(['up', '-d', '--wait'], 60)
        command(['exec', '-T', 'model-gateway', python, '-c',
                 "import ssl; assert ssl.create_default_context().cert_store_stats()['x509_ca'] > 0"])
        command(['exec', '-d', 'model-gateway', python, '/gateway/fake.py'])
        command(['exec', '-d', 'main', python, '/source/isolated_transport.py', 'local'])
        probe = """
import http.client,json,os,socket,time
assert os.listdir('/sys/class/net') == ['lo']
assert not os.path.exists('/var/run/docker.sock')
assert not os.path.exists('/gateway/config.json')
assert not os.path.exists('/source/mykey.py')
cap=[s for s in open('/proc/self/status') if s.startswith('CapEff:')][0]
assert int(cap.split()[1],16)==0
blocked=[]
for host in ['1.1.1.1','192.168.65.254','172.17.0.1','2606:4700:4700::1111']:
 try:
  s=socket.create_connection((host,443),timeout=1);s.close()
 except OSError:blocked.append(host)
assert len(blocked)==4
for i in range(50):
 try:
  conn=http.client.HTTPConnection('127.0.0.1',18765,timeout=2)
  conn.request('POST','/v1/traces',b'fixture')
  res=conn.getresponse();body=res.read();conn.close()
  if res.status==200:break
 except OSError:pass
 time.sleep(.1)
else:raise AssertionError('Socket stream not ready')
assert body==b'data: first\\n\\ndata: last\\n\\n'
for path in ['/v1/files','https://github.com/fyne-io/fyne','/v1/responses?url=https://github.com']:
 conn=http.client.HTTPConnection('127.0.0.1',18765,timeout=2)
 conn.request('POST',path,b'{}');res=conn.getresponse();assert res.status==400;res.read();conn.close()
conn=http.client.HTTPConnection('127.0.0.1',18765,timeout=2)
conn.request('POST','/v1/responses',b'{"model":"fixture","tools":[{"type":"web_search"}]}')
res=conn.getresponse();assert res.status==400;res.read();conn.close()
print(json.dumps({'only_loopback':True,'capabilities':0,'blocked_direct_targets':blocked,
'unix_stream_roundtrip':True,'arbitrary_fetch_blocked':True,'hosted_search_blocked':True,
'gateway_secrets_not_mounted':True}))
"""
        report['checks'] = json.loads(command(['exec', '-T', 'main', python, '-c', probe]))
        report['status'] = 'passed'
    except Exception as exc:
        report.update(status='failed', error=str(exc))
        raise
    finally:
        try:
            command(['down', '--volumes', '--remove-orphans'])
            report['fixture_resources_removed'] = True
        finally:
            (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--runtime', default=r'E:\LongContext\bench_runtime\m2\linux')
    args = parser.parse_args()
    print(json.dumps(run_check(args.output, args.runtime), indent=2))
