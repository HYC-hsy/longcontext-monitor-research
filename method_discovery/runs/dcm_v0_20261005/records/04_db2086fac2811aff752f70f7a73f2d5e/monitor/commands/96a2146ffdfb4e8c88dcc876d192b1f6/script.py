
import os
import glob

# Check endpoint package files
endpoint_files = sorted(glob.glob('/app/pkg/endpoint/*.go'))
print("Endpoint package files:")
for f in endpoint_files:
    print(f"  {os.path.basename(f)}")

# Check if deprecated.go exists
print(f"\ndeprecated.go exists: {os.path.exists('/app/pkg/endpoint/deprecated.go')}")
