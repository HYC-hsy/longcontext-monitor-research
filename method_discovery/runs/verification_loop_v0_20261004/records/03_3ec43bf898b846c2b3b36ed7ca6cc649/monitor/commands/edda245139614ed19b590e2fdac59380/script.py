
# Final comprehensive verification of all 6 targets
import subprocess
import os

print("="*60)
print("FINAL VERIFICATION OF ALL 6 TARGETS")
print("="*60)

results = {}

# Target 1: Streaming Types
print("\n[Target 1: Streaming Types]")
checks = []
files = [
    "/app/pkg/streaming/types.go",
    "/app/pkg/streaming/generic_client.go",
    "/app/pkg/streaming/generic_server.go"
]
for f in files:
    exists = os.path.exists(f)
    checks.append(exists)
    if not exists:
        print(f"✗ Missing: {f}")

result = subprocess.run(
    ["grep", "-c", "type ClientStream interface", "/app/pkg/streaming/types.go"],
    capture_output=True, text=True
)
has_clientstream = result.returncode == 0 and int(result.stdout.strip() or 0) > 0
checks.append(has_clientstream)

result = subprocess.run(
    ["grep", "-c", "ServerStream ServerStream", "/app/pkg/streaming/streaming.go"],
    capture_output=True, text=True
)
has_args_extension = result.returncode == 0 and int(result.stdout.strip() or 0) > 0
checks.append(has_args_extension)

results["Target 1"] = all(checks)
print(f"{'✓' if results['Target 1'] else '✗'} Target 1: {sum(checks)}/{len(checks)} checks passed")

# Target 2: Endpoint Architecture
print("\n[Target 2: Endpoint Architecture]")
checks = []
files = [
    "/app/pkg/endpoint/cep/endpoint.go",
    "/app/pkg/endpoint/sep/endpoint.go",
    "/app/pkg/endpoint/deprecated.go"
]
for f in files:
    exists = os.path.exists(f)
    checks.append(exists)
    if not exists:
        print(f"✗ Missing: {f}")

# Verify sep.StreamEndpoint takes ServerStream parameter
result = subprocess.run(
    ["grep", "type StreamEndpoint", "/app/pkg/endpoint/sep/endpoint.go"],
    capture_output=True, text=True
)
correct_sig = "st streaming.ServerStream" in result.stdout
checks.append(correct_sig)
if not correct_sig:
    print("✗ sep.StreamEndpoint has wrong signature")

# Verify DummyDummyMiddleware exists in cep
result = subprocess.run(
    ["grep", "-c", "func DummyDummyMiddleware", "/app/pkg/endpoint/cep/endpoint.go"],
    capture_output=True, text=True
)
has_dummy = result.returncode == 0 and int(result.stdout.strip() or 0) > 0
checks.append(has_dummy)

results["Target 2"] = all(checks)
print(f"{'✓' if results['Target 2'] else '✗'} Target 2: {sum(checks)}/{len(checks)} checks passed")

# Target 3: Transport Protocol
print("\n[Target 3: Transport Protocol]")
checks = []
result = subprocess.run(
    ["grep", "-A2", "TTHeaderStreaming.*=.*64", "/app/transport/keys.go"],
    capture_output=True, text=True
)
has_tt = "64" in result.stdout
checks.append(has_tt)

result = subprocess.run(
    ["grep", "-A2", "GRPCStreaming.*=.*128", "/app/transport/keys.go"],
    capture_output=True, text=True
)
has_grpc = "128" in result.stdout
checks.append(has_grpc)

result = subprocess.run(
    ["grep", "DefaultProtocol.*=.*Framed", "/app/transport/keys.go"],
    capture_output=True, text=True
)
has_default = result.returncode == 0
checks.append(has_default)

results["Target 3"] = all(checks)
print(f"{'✓' if results['Target 3'] else '✗'} Target 3: {sum(checks)}/{len(checks)} checks passed")

# Target 4: Thrift Codec Fallback
print("\n[Target 4: Thrift Codec Fallback]")
result = subprocess.run(
    ["grep", "-c", "fallback", "/app/pkg/remote/codec/thrift/thrift_data.go"],
    capture_output=True, text=True
)
has_fallback = result.returncode == 0 and int(result.stdout.strip() or 0) > 0
results["Target 4"] = has_fallback
print(f"{'✓' if results['Target 4'] else '✗'} Target 4: Fallback logic {'present' if has_fallback else 'missing'}")

# Target 5: Client Options
print("\n[Target 5: Client Options]")
checks = []
files = [
    "/app/client/option_unary.go",
    "/app/client/option_stream.go",
    "/app/client/option_ttstream.go",
    "/app/client/callopt/streamcall/streamcall.go"
]
for f in files:
    exists = os.path.exists(f)
    checks.append(exists)
    if not exists:
        print(f"✗ Missing: {f}")

results["Target 5"] = all(checks)
print(f"{'✓' if results['Target 5'] else '✗'} Target 5: {sum(checks)}/{len(checks)} checks passed")

# Target 6: gRPC Diagnostics
print("\n[Target 6: gRPC Diagnostics]")
checks = []
result = subprocess.run(
    ["grep", "-c", "func.*Dump.*interface", "/app/pkg/remote/trans/nphttp2/conn_pool.go"],
    capture_output=True, text=True
)
has_dump = result.returncode == 0 and int(result.stdout.strip() or 0) > 0
checks.append(has_dump)

result = subprocess.run(
    ["grep", "-c", "readAndCheckFrameHeader", "/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go"],
    capture_output=True, text=True
)
has_method = result.returncode == 0 and int(result.stdout.strip() or 0) > 0
checks.append(has_method)

results["Target 6"] = all(checks)
print(f"{'✓' if results['Target 6'] else '✗'} Target 6: {sum(checks)}/{len(checks)} checks passed")

print("\n" + "="*60)
print("OVERALL SUMMARY")
print("="*60)
for target, passed in results.items():
    print(f"{'✓' if passed else '✗'} {target}: {'PASS' if passed else 'FAIL'}")

all_pass = all(results.values())
print(f"\n{'✅ ALL TARGETS VERIFIED' if all_pass else '❌ SOME TARGETS INCOMPLETE'}")
print(f"Final: {sum(results.values())}/6 targets complete")
