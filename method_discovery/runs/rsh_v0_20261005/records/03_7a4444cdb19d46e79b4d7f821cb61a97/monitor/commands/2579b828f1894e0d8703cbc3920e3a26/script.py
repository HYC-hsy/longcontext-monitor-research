
import subprocess

print("=== Verifying Target 3: Default Protocol Change ===\n")

# Check if default protocol was changed to Framed in rpcconfig.go
result = subprocess.run(
    "grep -n 'transportProtocol.*Framed' /app/pkg/rpcinfo/rpcconfig.go",
    shell=True, capture_output=True, text=True
)
if result.returncode == 0 and result.stdout.strip():
    print("✓ Found Framed in rpcconfig.go:")
    print(result.stdout)
else:
    print("✗ No Framed default found")

# Check the initialize method more specifically
result = subprocess.run(
    "grep -A 5 'func.*initialize' /app/pkg/rpcinfo/rpcconfig.go | grep -i transport",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("\nTransport initialization context:")
    print(result.stdout)

print("\n=== Verifying Target 4: unmarshalThriftData Fix ===\n")

# Check if Basic codec block was removed from unmarshalThriftData
result = subprocess.run(
    "grep -n -A 8 'try fallback' /app/pkg/remote/codec/thrift/thrift_data.go | head -20",
    shell=True, capture_output=True, text=True
)
print("Fallback sections in thrift_data.go:")
print(result.stdout if result.stdout else "(no matches)")

if "if c.CodecType != Basic" in result.stdout or "if codec != Basic" in result.stdout:
    print("\n✗ ISSUE: Basic codec block still present in unmarshalThriftData")
else:
    print("\n✓ Basic codec block removed from unmarshalThriftData")
