
# Check what exists in key packages
import os

packages_to_check = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint', 
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2',
    '/app/transport',
    '/app/client'
]

for pkg in packages_to_check:
    print(f"\n=== {pkg} ===")
    if os.path.exists(pkg):
        files = sorted([f for f in os.listdir(pkg) if f.endswith('.go')])
        for f in files:
            print(f"  {f}")
    else:
        print("  [DOES NOT EXIST]")
