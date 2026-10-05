
import os

# Look for build/test infrastructure
build_files = []
for root, dirs, files in os.walk('/app'):
    if root.count('/') > 3:  # Limit depth
        continue
    for f in files:
        if f in ['Makefile', 'makefile', 'build.sh', 'test.sh', '.github']:
            build_files.append(os.path.join(root, f))

print("Build/test files:")
for f in build_files[:10]:
    print(f)

# Check for internal/client package structure (where option types come from)
internal_client = '/app/internal/client'
if os.path.exists(internal_client):
    files = os.listdir(internal_client)
    print(f"\n/app/internal/client exists with {len(files)} files:")
    print([f for f in files if f.endswith('.go')][:10])
else:
    print(f"\n{internal_client} does NOT exist")
