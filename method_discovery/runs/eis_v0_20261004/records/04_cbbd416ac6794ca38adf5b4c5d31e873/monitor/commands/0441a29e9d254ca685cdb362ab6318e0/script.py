
import os
import subprocess

print("=== Target 2 Missing Requirements Check ===\n")

# 1. Check for UnaryEndpoint in base pkg/endpoint package
print("1. UnaryEndpoint in BASE pkg/endpoint package:")
result = subprocess.run(['grep', '-n', 'type UnaryEndpoint', '/app/pkg/endpoint/endpoint.go'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print("  ✓ Found in endpoint.go:")
    print("  ", result.stdout.strip())
else:
    print("  ✗ NOT found in base pkg/endpoint/endpoint.go")
    print("  Note: Found in cep and sep packages instead (incorrect location)")

# 2. Check for deprecated.go file
print("\n2. deprecated.go file:")
deprecated_exists = os.path.exists('/app/pkg/endpoint/deprecated.go')
if deprecated_exists:
    print("  ✓ pkg/endpoint/deprecated.go exists")
    result = subprocess.run(['wc', '-l', '/app/pkg/endpoint/deprecated.go'],
                          capture_output=True, text=True)
    print(f"    {result.stdout.strip()}")
else:
    print("  ✗ pkg/endpoint/deprecated.go does NOT exist")

# 3. Check if ToMiddleware/ToUnaryMiddleware conversion methods exist
print("\n3. Conversion methods (ToMiddleware, ToUnaryMiddleware):")
result = subprocess.run(['grep', '-rn', 'ToMiddleware\\|ToUnaryMiddleware', '/app/pkg/endpoint/'],
                       capture_output=True, text=True)
if result.returncode == 0:
    print("  ✓ Conversion methods found:")
    for line in result.stdout.strip().split('\n')[:5]:
        print(f"    {line}")
else:
    print("  ✗ No conversion methods found")

print("\n=== SUMMARY ===")
print("Target 2 has TWO missing requirements:")
print("  1. UnaryEndpoint must be in pkg/endpoint (base), not just cep/sep")
print("  2. deprecated.go file must exist with RecvEndpoint/SendEndpoint types")
