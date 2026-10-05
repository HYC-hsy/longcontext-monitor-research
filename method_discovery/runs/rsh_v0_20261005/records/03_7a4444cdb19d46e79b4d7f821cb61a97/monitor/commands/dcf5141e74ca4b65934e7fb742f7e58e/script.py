
import subprocess

print("=== Detailed Target 5 Missing Items Check ===\n")

print("1. TailOption - broader search:")
result = subprocess.run(
    "find /app -name '*.go' -path '*/client/*' | xargs grep -l 'TailOption' 2>/dev/null",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print(f"Found TailOption in:\n{result.stdout}")
    # Get the actual definition
    result2 = subprocess.run(
        f"grep -n 'func TailOption' {result.stdout.strip().split()[0]} 2>/dev/null",
        shell=True, capture_output=True, text=True
    )
    print(f"Definition: {result2.stdout if result2.stdout else 'not a function'}")
else:
    print("✗ TailOption NOT FOUND anywhere in client/")

print("\n2. WithRecvTimeout stream call option:")
result = subprocess.run(
    "find /app -path '*/callopt*' -name '*.go' 2>/dev/null",
    shell=True, capture_output=True, text=True
)
print(f"callopt files found:\n{result.stdout if result.stdout else '(none)'}")

result = subprocess.run(
    "grep -rn 'WithRecvTimeout' /app/client/ 2>/dev/null | head -5",
    shell=True, capture_output=True, text=True
)
if result.stdout.strip():
    print(f"✓ WithRecvTimeout found:\n{result.stdout}")
else:
    print("✗ WithRecvTimeout NOT FOUND in client/")

print("\n3. Retry field migration - check WithFailureRetry implementation:")
result = subprocess.run(
    "grep -A 10 'func WithFailureRetry' /app/client/option.go 2>/dev/null",
    shell=True, capture_output=True, text=True
)
if "UnaryOptions.RetryMethodPolicies" in result.stdout:
    print("✓ WithFailureRetry uses UnaryOptions.RetryMethodPolicies")
elif "o.RetryMethodPolicies" in result.stdout and "UnaryOptions" not in result.stdout:
    print("✗ WithFailureRetry still uses old o.RetryMethodPolicies (not migrated)")
else:
    print(f"? WithFailureRetry implementation:\n{result.stdout[:300]}")
