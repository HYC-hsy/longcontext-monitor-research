
import os
files = os.listdir("/app/pkg/endpoint")
print("Files in pkg/endpoint:")
for f in sorted(files):
    print(f"  {f}")
