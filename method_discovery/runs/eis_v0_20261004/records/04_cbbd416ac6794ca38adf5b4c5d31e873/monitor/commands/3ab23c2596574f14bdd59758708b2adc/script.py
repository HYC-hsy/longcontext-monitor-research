
import os
import subprocess

# Check what files exist in pkg/streaming/
files = os.listdir('/app/pkg/streaming/')
go_files = [f for f in files if f.endswith('.go')]

print("Go files in pkg/streaming/:")
for f in sorted(go_files):
    print(f"  {f}")

# Check if streaming_new.go exists
if 'streaming_new.go' in go_files:
    print("\nstreaming_new.go exists separately")
else:
    print("\nstreaming_new.go does NOT exist")

# Try to understand what happened - check first few lines of streaming.go
result = subprocess.run(['head', '-n', '100', '/app/pkg/streaming/streaming.go'], 
                       capture_output=True, text=True)
print("\nFirst 100 lines of streaming.go:")
print(result.stdout)
