
import os

# Check what files exist in endpoint directory
endpoint_files = os.listdir("/app/pkg/endpoint")
print("Files in pkg/endpoint:")
for f in sorted(endpoint_files):
    print(f"  {f}")

# Check if deprecated.go exists
if "deprecated.go" in endpoint_files:
    print("\n✓ deprecated.go exists")
else:
    print("\n❌ deprecated.go NOT FOUND")
