
import os
import subprocess

# Check for go.mod to understand the project structure
if os.path.exists('/app/go.mod'):
    with open('/app/go.mod', 'r') as f:
        print("=== go.mod ===")
        print(f.read()[:500])
        
# Check if there are any test files related to the targets
test_dirs = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/transport',
    '/app/pkg/remote/codec/thrift',
    '/app/client'
]

print("\n=== Test files in key directories ===")
for dir in test_dirs:
    if os.path.exists(dir):
        test_files = [f for f in os.listdir(dir) if f.endswith('_test.go')]
        if test_files:
            print(f"{dir}: {len(test_files)} test files")
