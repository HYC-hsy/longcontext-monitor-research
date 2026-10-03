
import os
import json

# Get workspace structure
structure = {}
for root, dirs, files in os.walk('/app'):
    # Skip hidden and vendor directories
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['vendor', 'testdata']]
    level = root.replace('/app', '').count(os.sep)
    if level < 3:  # Limit depth
        rel_path = root.replace('/app/', '') if root != '/app' else 'root'
        go_files = [f for f in files if f.endswith('.go') and not f.endswith('_test.go')]
        if go_files:
            structure[rel_path] = go_files[:10]  # Limit files shown

for path in sorted(structure.keys())[:20]:
    print(f"{path}: {', '.join(structure[path][:5])}")
