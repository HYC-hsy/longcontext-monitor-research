
import subprocess
import os

print("=== Target 5 Verification: Client Option Category System ===\n")

# Check required files exist
files = {
    "internal/client/option_unary.go": False,
    "internal/client/option_stream.go": False,
    "internal/client/option_ttstream.go": False,
    "client/callopt/streamcall/streamcall.go": False,  # for WithRecvTimeout
}

for path, _ in files.items():
    full_path = f"/app/{path}"
    files[path] = os.path.exists(full_path)
    print(f"{'✓' if files[path] else '✗'} {path}: {'EXISTS' if files[path] else 'MISSING'}")

print("\n--- Checking Option Type Aliases in internal/client/option.go ---")
result = subprocess.run(
    "grep -n 'type.*Option' /app/internal/client/option.go | grep -E 'UnaryOption|StreamOption|TTHeaderStreamingOption' | head -5",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("✓ Found option type definitions:")
    print(result.stdout)
else:
    print("✗ Option type aliases not found")

print("\n--- Checking TailOption in client/option.go ---")
result = subprocess.run(
    "grep -n 'TailOption' /app/client/option.go",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("✓ TailOption found")
else:
    print("✗ TailOption not found")

print("\n--- Checking Retry Field Migration to UnaryOptions ---")
result = subprocess.run(
    "grep -n 'UnaryOptions.*Retry' /app/internal/client/option.go | head -3",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("✓ Found retry fields in UnaryOptions context")
else:
    print("? Retry fields migration unclear")

print("\n--- Checking WithRecvTimeout in callopt ---")
# Check if streamcall directory/file exists for WithRecvTimeout
result = subprocess.run(
    "find /app -path '*/client/callopt*' -name '*.go' | xargs grep -l 'WithRecvTimeout' 2>/dev/null",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print(f"✓ WithRecvTimeout found in: {result.stdout.strip()}")
else:
    print("✗ WithRecvTimeout not found in callopt")
