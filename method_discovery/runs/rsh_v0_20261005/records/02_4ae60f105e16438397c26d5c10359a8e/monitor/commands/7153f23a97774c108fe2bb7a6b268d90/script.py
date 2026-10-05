
import os
import json

# Get directory structure
result = {}
for root, dirs, files in os.walk('/app'):
    # Skip hidden, vendor, and test data dirs
    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['vendor', 'testdata']]
    
    level = root.replace('/app', '').count(os.sep)
    if level > 2:  # Limit depth
        continue
    
    indent = ' ' * 2 * level
    rel_path = root.replace('/app/', '') if root != '/app' else 'root'
    go_files = [f for f in files if f.endswith('.go') and not f.endswith('_test.go')]
    if go_files or level < 2:
        print(f"{indent}{rel_path}: {len(go_files)} Go files")
        if level <= 1 and len(go_files) < 15:
            for f in sorted(go_files)[:10]:
                print(f"{indent}  - {f}")
