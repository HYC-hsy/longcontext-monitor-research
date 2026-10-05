
import subprocess

print("=== VERIFYING CRITICAL REQUIREMENTS ===\n")

print("1. RETRY MIGRATION (Target 5 req 7)")
print("-" * 50)
# Check WithFailureRetry implementation
result = subprocess.run("grep -A 15 'func WithFailureRetry' /app/client/option.go", shell=True, capture_output=True, text=True)
print("WithFailureRetry implementation:")
print(result.stdout[:500] if result.stdout else "NOT FOUND")

# Check if Options struct has UnaryOptions field
print("\n2. OPTIONS STRUCT FIELDS")
print("-" * 50)
result = subprocess.run("grep -n 'UnaryOptions\\|StreamMiddleware' /app/internal/client/option.go | head -20", shell=True, capture_output=True, text=True)
print("UnaryOptions/Middleware fields in Options struct:")
print(result.stdout if result.stdout else "NOT FOUND")

print("\n3. DUMP() PANIC-SAFE (Target 6 req 1)")
print("-" * 50)
result = subprocess.run("grep -A 30 'func.*Dump.*interface' /app/pkg/remote/trans/nphttp2/conn_pool.go | head -35", shell=True, capture_output=True, text=True)
print("Dump() implementation (first 35 lines):")
print(result.stdout if result.stdout else "NOT FOUND")

print("\n4. BUILD STATUS")
print("-" * 50)
result = subprocess.run("cd /app && go build ./... 2>&1 | head -10", shell=True, capture_output=True, text=True)
if result.returncode == 0 and not result.stdout.strip():
    print("✓ BUILD SUCCESSFUL")
else:
    print(f"Build output: {result.stdout[:300]}")
