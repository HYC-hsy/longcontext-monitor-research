
# Quick verification of each target's key requirements
import subprocess

checks = []

# Target 1: Check for ClientStream/ServerStream interfaces
print("=== Target 1: Streaming Types ===")
result = subprocess.run(
    ["grep", "-c", "type ClientStream interface", "/app/pkg/streaming/types.go"],
    capture_output=True, text=True
)
t1_client = result.returncode == 0 and int(result.stdout.strip() or 0) > 0

result = subprocess.run(
    ["grep", "-c", "type ServerStream interface", "/app/pkg/streaming/types.go"],
    capture_output=True, text=True
)
t1_server = result.returncode == 0 and int(result.stdout.strip() or 0) > 0

if t1_client and t1_server:
    print("✓ ClientStream and ServerStream interfaces exist")
    checks.append(True)
else:
    print("✗ Missing ClientStream or ServerStream interface")
    checks.append(False)

# Target 2: Check sep.StreamEndpoint signature  
print("\n=== Target 2: Endpoints ===")
result = subprocess.run(
    ["grep", "type StreamEndpoint", "/app/pkg/endpoint/sep/endpoint.go"],
    capture_output=True, text=True
)
if "st streaming.ServerStream" in result.stdout:
    print("✓ sep.StreamEndpoint has correct signature (takes ServerStream)")
    checks.append(True)
else:
    print("✗ sep.StreamEndpoint signature incorrect")
    checks.append(False)

# Target 3: Check protocol constants
print("\n=== Target 3: Transport Protocols ===")
result = subprocess.run(
    ["grep", "-E", "TTHeaderStreaming.*=.*64|GRPCStreaming.*=.*128", "/app/transport/keys.go"],
    capture_output=True, text=True
)
if "TTHeaderStreaming" in result.stdout and "GRPCStreaming" in result.stdout:
    print("✓ TTHeaderStreaming=64 and GRPCStreaming=128 present")
    checks.append(True)
else:
    print("✗ Protocol constants missing")
    checks.append(False)

# Target 5: Check required option files
print("\n=== Target 5: Client Options ===")
import os
t5_files = [
    "/app/client/option_unary.go",
    "/app/client/option_stream.go",
    "/app/client/option_ttstream.go"
]
if all(os.path.exists(f) for f in t5_files):
    print("✓ All required option files exist")
    checks.append(True)
else:
    print("✗ Some option files missing")
    checks.append(False)

print(f"\n{'='*50}")
print(f"Summary: {sum(checks)}/4 key checks passed")
