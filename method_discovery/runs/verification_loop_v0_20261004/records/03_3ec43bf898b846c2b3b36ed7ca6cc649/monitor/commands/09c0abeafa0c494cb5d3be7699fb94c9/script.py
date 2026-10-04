
# Final verification of critical requirements
import subprocess
import os

checks = []

# Target 3: Verify transport protocol constant values
print("=== Target 3: Protocol Constants ===")
result = subprocess.run(
    ["grep", "-A", "10", "^const (", "/app/transport/keys.go"],
    capture_output=True, text=True
)
if "TTHeader    Protocol = 2" in result.stdout and \
   "TTHeaderStreaming Protocol = 64" in result.stdout and \
   "GRPCStreaming     Protocol = 128" in result.stdout:
    print("✓ Protocol constants have correct values")
    checks.append(True)
else:
    print("✗ Protocol constants are incorrect")
    print(result.stdout)
    checks.append(False)

# Target 5: Verify required files exist
print("\n=== Target 5: Required Files ===")
required_t5 = [
    "/app/client/option_unary.go",
    "/app/client/option_stream.go",
    "/app/client/option_ttstream.go",
    "/app/client/callopt/streamcall/streamcall.go"
]
all_exist = all(os.path.exists(f) for f in required_t5)
if all_exist:
    print("✓ All required Target 5 files exist")
    checks.append(True)
else:
    print("✗ Some Target 5 files missing")
    checks.append(False)

# Target 2: Verify sep.StreamEndpoint signature
print("\n=== Target 2: sep.StreamEndpoint Signature ===")
result = subprocess.run(
    ["grep", "type StreamEndpoint", "/app/pkg/endpoint/sep/endpoint.go"],
    capture_output=True, text=True
)
if "st streaming.ServerStream" in result.stdout and "err error" in result.stdout:
    print("✓ sep.StreamEndpoint has correct signature (takes ServerStream)")
    checks.append(True)
else:
    print("✗ sep.StreamEndpoint signature incorrect")
    print(result.stdout)
    checks.append(False)

print(f"\n=== Summary: {sum(checks)}/{len(checks)} checks passed ===")
