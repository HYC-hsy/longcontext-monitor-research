
# Check for UnaryEndpoint in pkg/endpoint package
import subprocess

print("=== Checking Target 2: UnaryEndpoint requirement ===\n")

# Search for UnaryEndpoint in all endpoint files
result = subprocess.run(
    ['grep', '-rn', 'type UnaryEndpoint', '/app/pkg/endpoint/'],
    capture_output=True, text=True
)

if result.returncode == 0:
    print("✓ UnaryEndpoint found:")
    print(result.stdout)
else:
    print("✗ UnaryEndpoint NOT found in pkg/endpoint/")
    
# Check for UnaryMiddleware and related types
print("\n--- Checking for related unary types ---")
result = subprocess.run(
    ['grep', '-rn', 'UnaryMiddleware\|UnaryChain', '/app/pkg/endpoint/'],
    capture_output=True, text=True
)

if result.returncode == 0:
    print("Related unary types found:")
    print(result.stdout[:500])
else:
    print("No UnaryMiddleware types found")

# List all .go files in endpoint package
print("\n--- Files in pkg/endpoint/ ---")
import os
for f in sorted(os.listdir('/app/pkg/endpoint/')):
    if f.endswith('.go'):
        print(f"  {f}")
