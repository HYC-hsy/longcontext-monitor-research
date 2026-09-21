import datetime
import importlib.util
import socket
import ssl
import sys
import threading
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_PATH = ROOT / "long_context_bench/adapters/isolated_transport.py"
PREFLIGHT_PATH = ROOT / "method_discovery/run_dcec_transport_equivalence_preflight.py"


def load_transport():
    spec = importlib.util.spec_from_file_location("isolated_transport_tls_test", TRANSPORT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_preflight():
    spec = importlib.util.spec_from_file_location("dcec_transport_equivalence_test", PREFLIGHT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def issue_ca_and_server(root: Path, prefix: str, hostname: str = "localhost"):
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"{prefix} test CA")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - datetime.timedelta(minutes=1))
          .not_valid_after(now + datetime.timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .sign(ca_key, hashes.SHA256()))
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    server = (x509.CertificateBuilder().subject_name(server_name).issuer_name(ca.subject)
              .public_key(server_key.public_key()).serial_number(x509.random_serial_number())
              .not_valid_before(now - datetime.timedelta(minutes=1))
              .not_valid_after(now + datetime.timedelta(days=1))
              .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
              .sign(ca_key, hashes.SHA256()))
    ca_path, cert_path, key_path = (root / f"{prefix}-{name}" for name in
                                    ("ca.pem", "server.pem", "server-key.pem"))
    ca_path.write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(server.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(server_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption()))
    return ca_path, cert_path, key_path


def serve_once(cert_path: Path, key_path: Path):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)

    def run():
        connection, _ = listener.accept()
        try:
            with context.wrap_socket(connection, server_side=True):
                pass
        except (ssl.SSLError, OSError):
            connection.close()
        finally:
            listener.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return port, thread


def handshake(context, port: int, hostname: str):
    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname=hostname):
            return True


def test_verified_tls_context_trusts_configured_ca(tmp_path):
    transport = load_transport()
    ca, cert, key = issue_ca_and_server(tmp_path, "trusted")
    port, thread = serve_once(cert, key)
    context = transport.create_tls_context({"tls": {
        "verification_enabled": True, "ca_file": str(ca)}})
    assert handshake(context, port, "localhost") is True
    thread.join(timeout=5)


def test_verified_tls_context_rejects_missing_signing_ca(tmp_path):
    transport = load_transport()
    _, cert, key = issue_ca_and_server(tmp_path, "server")
    unrelated_ca, _, _ = issue_ca_and_server(tmp_path, "unrelated")
    port, thread = serve_once(cert, key)
    context = transport.create_tls_context({"tls": {
        "verification_enabled": True, "ca_file": str(unrelated_ca)}})
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(context, port, "localhost")
    thread.join(timeout=5)


def test_verified_tls_context_rejects_hostname_mismatch(tmp_path):
    transport = load_transport()
    ca, cert, key = issue_ca_and_server(tmp_path, "hostname")
    port, thread = serve_once(cert, key)
    context = transport.create_tls_context({"tls": {
        "verification_enabled": True, "ca_file": str(ca)}})
    with pytest.raises(ssl.SSLCertVerificationError):
        handshake(context, port, "wrong.example")
    thread.join(timeout=5)


@pytest.mark.parametrize("base,operation", [
    ("https://example.test", "messages"),
    ("https://example.test/v1", "messages"),
    ("https://example.test/v2", "messages"),
    ("https://example.test/v1/messages", "messages"),
    ("https://example.test/custom$", "messages"),
])
def test_gateway_url_builder_matches_production_special_cases(base, operation):
    transport = load_transport()
    sys.path.insert(0, str(ROOT / "GenericAgent-main"))
    from monitor_agent_core.provider import _url
    assert transport.provider_url(base, operation) == _url(base, operation)


def test_full_gateway_handler_forwards_frozen_application_semantics():
    preflight = load_preflight()
    profile = {
        "provider": "anthropic", "api_mode": "messages", "apikey": "FIXTURE",
        "apibase": "https://example.invalid", "model": "claude-opus-4-8",
        "transport_route": "monitor", "thinking_type": "adaptive",
        "reasoning_effort": "high", "temperature": 1, "max_tokens": 8192,
    }
    snapshot = {
        "system": "Frozen system", "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Frozen request"}]}], "tools": [],
    }
    result = preflight.full_forwarding_probe(profile, snapshot)
    assert result["status"] == "passed"
    assert result["x_model_route_forwarded"] is True
    assert result["user_agent_forwarded"] is True
    assert result["json_body_semantically_equal"] is True
    assert result["safe_gateway_stages"] == [
        "resolved", "connected", "request_sent",
        "response_headers_received", "response_stream_completed",
    ]
