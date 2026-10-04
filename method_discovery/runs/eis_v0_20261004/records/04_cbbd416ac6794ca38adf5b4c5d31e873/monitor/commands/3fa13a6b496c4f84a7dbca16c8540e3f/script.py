
import os
import subprocess

# Check if client/callopt/streamcall directory exists and has WithRecvTimeout
callopt_path = '/app/client/callopt/streamcall'
if os.path.exists(callopt_path):
    files = os.listdir(callopt_path)
    print(f"Files in {callopt_path}:")
    for f in files:
        print(f"  {f}")
    
    # Search for WithRecvTimeout
    result = subprocess.run(
        ['grep', '-r', 'WithRecvTimeout', callopt_path],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"\n✓ WithRecvTimeout found in streamcall package")
        print(result.stdout[:500])
    else:
        print(f"\n✗ WithRecvTimeout NOT found in streamcall package")
else:
    print(f"✗ Directory {callopt_path} does NOT exist")

# Check if retry/fallback options were migrated to UnaryOptions
print("\n\nChecking retry/fallback migration:")
result = subprocess.run(
    ['grep', '-A5', 'WithFailureRetry', '/app/client/option.go'],
    capture_output=True, text=True
)
if 'UnaryOptions.RetryMethodPolicies' in result.stdout:
    print("✓ WithFailureRetry migrated to UnaryOptions")
else:
    print("✗ WithFailureRetry NOT migrated to UnaryOptions")
    print("Current implementation:")
    print(result.stdout[:500])
