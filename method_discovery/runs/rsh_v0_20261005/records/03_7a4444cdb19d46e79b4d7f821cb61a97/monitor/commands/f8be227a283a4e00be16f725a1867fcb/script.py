
import subprocess

print("=== Verifying Target 5 Current State ===\n")

print("1. Checking what exists in client/option.go:")
result = subprocess.run(
    "grep -n 'func.*TailOption\\|func.*WithUnary\\|func.*WithStream\\|func.*WithTTHeader' /app/client/option.go | head -15",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("Found option functions:")
    print(result.stdout)
else:
    print("No Target 5 option functions found")

print("\n2. Checking WithRecvTimeout in callopt/streamcall:")
result = subprocess.run(
    "find /app/client/callopt/streamcall -name '*.go' | xargs grep -n 'func WithRecvTimeout' 2>/dev/null",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("✓ WithRecvTimeout found:")
    print(result.stdout)
else:
    print("✗ WithRecvTimeout not found")

print("\n3. Checking retry migration in client/option.go:")
result = subprocess.run(
    "grep -n 'WithFailureRetry\\|WithBackupRequest' /app/client/option.go | head -3",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print("Found retry functions at:")
    print(result.stdout)
    
    # Check if they use UnaryOptions
    result2 = subprocess.run(
        "grep -A 5 'func WithFailureRetry' /app/client/option.go | grep -i unary",
        shell=True, capture_output=True, text=True
    )
    if result2.stdout.strip():
        print("\n✓ Uses UnaryOptions")
    else:
        print("\n? Retry migration status unclear")

print("\n4. Current option file structure:")
result = subprocess.run(
    "ls -la /app/client/option*.go 2>/dev/null",
    shell=True, capture_output=True, text=True
)
print(result.stdout if result.stdout else "(no option_*.go files found)")
