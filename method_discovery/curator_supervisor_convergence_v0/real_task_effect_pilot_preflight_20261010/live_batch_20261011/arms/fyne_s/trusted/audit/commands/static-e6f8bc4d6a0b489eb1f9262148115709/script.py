
import os
import json

# Check workspace structure
result = {
    "root_files": [],
    "key_packages": {}
}

# List root Go files
for f in os.listdir('/app'):
    if f.endswith('.go') and os.path.isfile(f'/app/{f}'):
        result["root_files"].append(f)

# Check for key package directories
key_dirs = ['app', 'theme', 'data/binding', 'data/validation', 'driver/desktop', 'widget', 'container']
for dir_path in key_dirs:
    full_path = f'/app/{dir_path}'
    if os.path.exists(full_path) and os.path.isdir(full_path):
        go_files = [f for f in os.listdir(full_path) if f.endswith('.go') and not f.endswith('_test.go')]
        result["key_packages"][dir_path] = go_files[:10]  # First 10 files

print(json.dumps(result, indent=2))
