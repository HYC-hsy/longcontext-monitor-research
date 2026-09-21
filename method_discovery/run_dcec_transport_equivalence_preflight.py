"""Zero-model validation of production-provider / isolated-gateway equivalence."""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import http.client
import http.server
import importlib.util
import io
import json
import ssl
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


ROOT = Path(__file__).resolve().parents[1]
GA_ROOT = ROOT / "GenericAgent-main"
sys.path.insert(0, str(GA_ROOT))
sys.path.insert(0, str(ROOT / "method_discovery"))

from monitor_agent_core.provider import MonitorProviderClient  # noqa: E402
from dcec_record_isolation import (  # noqa: E402
    filesystem_probe,
    prepare_runtime,
    provider_deadline_probe,
    tls_handshake_probe,
)
from run_dcec_v0_discrimination import (  # noqa: E402
    anti_leakage_audit,
    load_json,
    materialize_visible,
    model_visible_projection,
    reset_directory,
    sha256_bytes,
    sha256_file,
    write_json,
)


MANIFEST = ROOT / "method_discovery/artifacts/dcec_v0_20260921/discriminating_manifest.json"
SMOKE_MANIFEST = ROOT / "method_discovery/artifacts/dcec_v0_20260921/infra_smoke_manifest.json"
OUTPUT = ROOT / "method_discovery/runs/dcec_v0_transport_equivalence_preflight_20260921"
CONFIG = ROOT / "monitor_config/models.local.json"
TRANSPORT = ROOT / "long_context_bench/adapters/isolated_transport.py"


def _load_transport():
    spec = importlib.util.spec_from_file_location("dcec_transport_preflight", TRANSPORT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _canonical_json_hash(value) -> str:
    return sha256_bytes(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _credential_scheme(headers: dict) -> str:
    lowered = {key.lower(): value for key, value in headers.items()}
    if "x-api-key" in lowered:
        return "x-api-key"
    if str(lowered.get("authorization") or "").startswith("Bearer "):
        return "authorization-bearer"
    return "missing-or-unsupported"


def production_request(profile: dict, snapshot: dict) -> tuple[str, dict, dict]:
    client = MonitorProviderClient("claude_monitor_opus48", dict(profile))
    client.system = snapshot["system"]
    client.history = json.loads(json.dumps(snapshot["messages"]))
    url, headers, payload = client._anthropic_request(snapshot["tools"])
    if client.config.get("transport_route"):
        headers["x-model-route"] = client.config["transport_route"]
    return url, headers, payload


def application_semantics(profile: dict, snapshot: dict) -> dict:
    transport = _load_transport()
    production_url, production_headers, production_body = production_request(profile, snapshot)
    incoming_path = "/v1/messages?beta=true"
    config = _gateway_config_for_profile(profile)
    forwarded = {key.lower(): value for key, value in production_headers.items()
                 if key.lower() in transport.FORWARD_HEADERS}
    gateway_url, credentials, gateway_body, _ = transport._resolve_request(
        incoming_path, json.dumps(production_body).encode("utf-8"), config,
        forwarded.get("x-model-route"))
    forwarded.update(credentials)
    production_normalized = {key.lower(): value for key, value in production_headers.items()}
    forwarded_normalized = {key.lower(): value for key, value in forwarded.items()}
    application_names = {
        "content-type", "accept", "anthropic-version", "anthropic-beta",
        "user-agent", "x-model-route",
    }
    application_equal = all(
        production_normalized.get(key) == forwarded_normalized.get(key)
        for key in application_names)
    url_equal = production_url == gateway_url
    body_equal = production_body == json.loads(gateway_body)
    credential_equal = (
        _credential_scheme(production_headers) == _credential_scheme(forwarded))
    if not (url_equal and application_equal and body_equal and credential_equal):
        raise ValueError("production/gateway application request semantics differ")
    parsed = urlsplit(production_url)
    return {
        "url_semantics_equal": url_equal,
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "port": parsed.port or 443,
        "path": parsed.path,
        "path_sha256": sha256_bytes(parsed.path.encode("utf-8")),
        "query_keys": sorted(key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)),
        "query_sha256": sha256_bytes(parsed.query.encode("utf-8")),
        "application_headers_equal": application_equal,
        "application_header_names": sorted(application_names),
        "x_model_route_forwarded": (
            forwarded_normalized.get("x-model-route")
            == production_normalized.get("x-model-route") == "monitor"),
        "user_agent_forwarded": (
            forwarded_normalized.get("user-agent")
            == production_normalized.get("user-agent") == "longcontext-monitor/1.0"),
        "credential_scheme": _credential_scheme(forwarded),
        "credential_scheme_equal": credential_equal,
        "json_body_semantically_equal": body_equal,
        "json_body_semantic_sha256": _canonical_json_hash(production_body),
    }


def _gateway_config_for_profile(profile: dict) -> dict:
    from dcec_record_isolation import _gateway_config
    return _gateway_config(profile)


def _issue_local_certificate(root: Path) -> tuple[Path, Path, Path]:
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "DCEC transport fixture CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - datetime.timedelta(minutes=1))
          .not_valid_after(now + datetime.timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .sign(ca_key, hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(ca.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    ca_path, cert_path, key_path = root / "ca.pem", root / "server.pem", root / "key.pem"
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    return ca_path, cert_path, key_path


def full_forwarding_probe(profile: dict, snapshot: dict) -> dict:
    """Run the real gateway Handler against a local trusted HTTPS upstream."""
    transport = _load_transport()
    _, production_headers, production_body = production_request(profile, snapshot)
    captured = {}

    class Upstream(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            size = int(self.headers["Content-Length"])
            captured.update(
                method="POST", path=self.path,
                headers={key.lower(): value for key, value in self.headers.items()},
                body=self.rfile.read(size))
            response = b'{"fixture":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    with tempfile.TemporaryDirectory(prefix="dcec-forwarding-") as temporary:
        root = Path(temporary)
        ca_path, cert_path, key_path = _issue_local_certificate(root)
        upstream = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_path, key_path)
        upstream.socket = context.wrap_socket(upstream.socket, server_side=True)
        upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        fake_credential = ({"x-api-key": "FIXTURE"}
                           if _credential_scheme(production_headers) == "x-api-key"
                           else {"Authorization": "Bearer FIXTURE"})
        route = {
            "base": f"https://localhost:{upstream.server_port}",
            "headers": fake_credential, "paths": ["/v1/messages"],
            "model": profile["model"],
            "tls": {"verification_enabled": True, "ca_file": str(ca_path)},
        }
        gateway = http.server.ThreadingHTTPServer(("127.0.0.1", 0), transport.Handler)
        gateway.mode = "gateway"
        gateway.config = {"models": {"monitor": route},
                          "telemetry": "http://127.0.0.1:9/v1/traces"}
        gateway_thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        diagnostics = io.StringIO()
        try:
            upstream_thread.start()
            gateway_thread.start()
            safe_headers = {key: value for key, value in production_headers.items()
                            if key.lower() not in {"authorization", "x-api-key"}}
            connection = http.client.HTTPConnection(*gateway.server_address, timeout=10)
            with contextlib.redirect_stderr(diagnostics):
                connection.request(
                    "POST", "/v1/messages?beta=true",
                    body=json.dumps(production_body).encode("utf-8"), headers=safe_headers)
                response = connection.getresponse()
                response.read()
            connection.close()
        finally:
            gateway.shutdown()
            gateway.server_close()
            upstream.shutdown()
            upstream.server_close()
            gateway_thread.join(timeout=5)
            upstream_thread.join(timeout=5)
    captured_headers = captured["headers"]
    expected_headers = {key.lower(): value for key, value in production_headers.items()
                        if key.lower() not in {"authorization", "x-api-key"}}
    compared = {
        "content-type", "accept", "anthropic-version", "anthropic-beta",
        "user-agent", "x-model-route",
    }
    headers_equal = all(captured_headers.get(key) == expected_headers.get(key)
                        for key in compared)
    body_equal = json.loads(captured["body"]) == production_body
    stages = []
    for line in diagnostics.getvalue().splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if item.get("event") == "gateway_transport":
            stages.append(item.get("stage"))
    required_stages = [
        "resolved", "connected", "request_sent",
        "response_headers_received", "response_stream_completed",
    ]
    if (response.status != 200 or captured.get("method") != "POST"
            or captured.get("path") != "/v1/messages?beta=true"
            or not headers_equal or not body_equal
            or any(stage not in stages for stage in required_stages)):
        raise ValueError("local HTTPS full-forwarding equivalence failed")
    return {
        "status": "passed", "method": captured["method"],
        "path": captured["path"], "application_headers_equal": headers_equal,
        "compared_application_headers": sorted(compared),
        "x_model_route_forwarded": captured_headers.get("x-model-route") == "monitor",
        "user_agent_forwarded": (
            captured_headers.get("user-agent") == "longcontext-monitor/1.0"),
        "credential_scheme": _credential_scheme(captured_headers),
        "json_body_semantically_equal": body_equal,
        "json_body_semantic_sha256": _canonical_json_hash(production_body),
        "safe_gateway_stages": stages,
        "provider_http_requests": 0, "model_api_calls": 0,
    }


def run_preflight(output: Path = OUTPUT) -> dict:
    if output.exists():
        raise FileExistsError(f"transport preflight already exists: {output}")
    if not SMOKE_MANIFEST.is_file():
        raise FileNotFoundError("frozen infrastructure smoke manifest is missing")
    output.mkdir(parents=True)
    manifest = load_json(MANIFEST)
    spec = load_json(ROOT / manifest["fixture_spec"])
    profiles = load_json(CONFIG)
    profile = profiles[manifest["shared_contract"]["supervisor_profile"]]
    runtime = prepare_runtime(
        output / "isolated_runtime", profile,
        manifest["historical_candidate_config_keys"])
    with tempfile.TemporaryDirectory(prefix="dcec-transport-preflight-", dir=output) as temp:
        scratch = Path(temp)
        audit = anti_leakage_audit(manifest, spec, scratch, output / "isolated_runtime")
        expected = manifest["expected_scientific_request_sha256"]
        actual = {"ordinary": audit["ordinary_request_sha256"],
                  "dcec_v0": audit["dcec_request_sha256"]}
        if actual != expected:
            raise ValueError("scientific request hashes changed")
        slot = reset_directory(scratch, scratch / "record")
        materialize_visible(slot, model_visible_projection(spec, "latent_defect"))
        from dcec_record_isolation import request_probe
        snapshot = request_probe(output / "isolated_runtime", slot, False)
        application = application_semantics(profile, snapshot)
        forwarding = full_forwarding_probe(profile, snapshot)
        filesystem = filesystem_probe(output / "isolated_runtime", slot)
        deadline = provider_deadline_probe(
            output / "isolated_runtime", slot,
            manifest["execution_constraints"]["record_wall_seconds"])
    tls = tls_handshake_probe(profile)
    smoke = load_json(SMOKE_MANIFEST)
    if smoke.get("execution_authorized") is not False:
        raise ValueError("infrastructure smoke must remain unauthorized")
    result = {
        "schema_version": "dcec-transport-equivalence-preflight/1",
        "status": "passed_not_executed",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             text=True).strip(),
        "transport_source_sha256": sha256_file(TRANSPORT),
        "isolation_source_sha256": sha256_file(
            ROOT / "method_discovery/dcec_record_isolation.py"),
        "preflight_runner_sha256": sha256_file(Path(__file__)),
        "mechanism_implementation": manifest["implementation_commit"],
        "mechanism_source_sha256": manifest["mechanism_source_sha256"],
        "fixture_sha256": sha256_file(ROOT / manifest["fixture_spec"]),
        "scientific_request_invariance": {
            "expected": expected, "actual": actual, "unchanged": actual == expected},
        "production_gateway_application_equivalence": application,
        "local_https_full_forwarding": forwarding,
        "real_upstream_tls_handshake": tls,
        "code_run_filesystem_isolation": filesystem,
        "provider_deadline": deadline,
        "isolated_runtime": runtime,
        "infra_smoke": {
            "manifest": SMOKE_MANIFEST.relative_to(ROOT).as_posix(),
            "execution_authorized": False,
            "classification": smoke["classification"],
            "executed": False,
        },
        "provider_http_requests": 0,
        "model_api_calls": 0,
    }
    write_json(output / "preflight.json", result)
    return result


if __name__ == "__main__":
    run_preflight()
