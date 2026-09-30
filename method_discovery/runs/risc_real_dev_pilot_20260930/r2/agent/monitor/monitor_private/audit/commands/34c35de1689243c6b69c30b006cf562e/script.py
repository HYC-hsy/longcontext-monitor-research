
import os
import json

# Get directory structure
def get_directory_structure(path, max_depth=3, current_depth=0):
    result = []
    if current_depth >= max_depth:
        return result
    
    try:
        items = sorted(os.listdir(path))
        for item in items:
            if item.startswith('.'):
                continue
            full_path = os.path.join(path, item)
            if os.path.isdir(full_path):
                result.append(f"{'  ' * current_depth}{item}/")
                result.extend(get_directory_structure(full_path, max_depth, current_depth + 1))
    except PermissionError:
        pass
    return result

# Look at key directories
print("=== Package structure ===")
pkg_structure = get_directory_structure('/app/pkg', max_depth=2)
for line in pkg_structure[:50]:
    print(line)

print("\n=== Client package ===")
client_files = []
if os.path.exists('/app/client'):
    client_files = [f for f in os.listdir('/app/client') if f.endswith('.go')]
    print(f"Files: {sorted(client_files)[:15]}")
