
# Check Target 4: Verify Basic codec fallback was enabled
import subprocess

print("=== Target 4 Verification: Basic Codec Fallback ===\n")

# Check Marshal function - should NOT have "if c.CodecType != Basic" blocking fallback
print("1. Checking Marshal function in thrift.go:")
result = subprocess.run(
    "grep -n -A 10 'fallback to frugal or fastcodec' /app/pkg/remote/codec/thrift/thrift.go",
    shell=True, capture_output=True, text=True
)
if result.returncode == 0:
    print(result.stdout)
    if "if c.CodecType != Basic" in result.stdout:
        print("✗ ISSUE: Basic codec is still blocked from fallback in Marshal")
    else:
        print("✓ Marshal: Basic codec block removed or not present in fallback section")

print("\n2. Checking unmarshalThriftData in thrift_data.go:")
result = subprocess.run(
    "grep -n -B 2 -A 8 'try.*fallback' /app/pkg/remote/codec/thrift/thrift_data.go",
    shell=True, capture_output=True, text=True
)
if result.returncode == 0:
    print(result.stdout)
    if "if codec != Basic" in result.stdout or "if c.CodecType != Basic" in result.stdout:
        print("✗ ISSUE: Basic codec is still blocked from fallback in unmarshalThriftData")
    else:
        print("✓ unmarshalThriftData: Basic codec block removed or not present")

print("\n=== Target 3 Verification: Default Protocol Change ===\n")

# Check for default protocol change from PurePayload to Framed
print("3. Checking for default protocol initialization (PurePayload=0 to Framed):")
locations = [
    "/app/client/option.go",
    "/app/internal/client/option.go",
    "/app/server/option.go",
]

found_any = False
for loc in locations:
    result = subprocess.run(
        f"grep -n 'transport.Framed' {loc} 2>/dev/null | head -5",
        shell=True, capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        print(f"\nFound in {loc}:")
        print(result.stdout[:500])
        found_any = True

if not found_any:
    print("✗ ISSUE: No default protocol change to Framed found in option files")
    print("   Task requires: 'change the default transport protocol from buffered (PurePayload) to Framed'")
