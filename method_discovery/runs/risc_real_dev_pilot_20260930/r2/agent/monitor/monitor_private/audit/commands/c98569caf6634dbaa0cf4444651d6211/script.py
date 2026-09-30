
import os

# Check for key packages mentioned in the task
key_paths = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/pkg/remote/codec/thrift',
    '/app/transport',
    '/app/pkg/remote/trans/nphttp2',
]

print("=== Checking for existing key packages ===")
for path in key_paths:
    exists = os.path.exists(path)
    print(f"{path}: {'EXISTS' if exists else 'NOT FOUND'}")
    if exists and os.path.isdir(path):
        files = [f for f in os.listdir(path) if f.endswith('.go')]
        if files:
            print(f"  Files: {sorted(files)[:5]}")

# Check transport package location
print("\n=== Looking for transport package ===")
for root, dirs, files in os.walk('/app'):
    if 'transport.go' in files or 'protocol.go' in files:
        print(f"Found in: {root}")
        relevant_files = [f for f in files if f.endswith('.go') and ('transport' in f or 'protocol' in f)]
        print(f"  Files: {relevant_files[:5]}")
        break
