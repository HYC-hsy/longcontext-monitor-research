
import os
import glob

# Check for Target 5 specific files
target5_files = [
    '/app/client/option_unary.go',
    '/app/client/option_stream.go', 
    '/app/client/option_ttstream.go'
]

print("Target 5 required files:")
for f in target5_files:
    exists = os.path.exists(f)
    print(f"  {os.path.basename(f)}: {exists}")

# Check for Target 2 deprecated.go
print("\nTarget 2 required file:")
print(f"  deprecated.go: {os.path.exists('/app/pkg/endpoint/deprecated.go')}")

# List all client option files to see what was created
print("\nActual client option files:")
for f in sorted(glob.glob('/app/client/option*.go')):
    print(f"  {os.path.basename(f)}")
