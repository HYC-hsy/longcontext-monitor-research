
import os
import json

# Get directory structure
def get_structure(path, max_depth=2, current_depth=0):
    items = []
    if current_depth >= max_depth:
        return items
    
    try:
        for item in sorted(os.listdir(path)):
            if item.startswith('.'):
                continue
            item_path = os.path.join(path, item)
            if os.path.isdir(item_path):
                items.append(f"{'  ' * current_depth}{item}/")
                items.extend(get_structure(item_path, max_depth, current_depth + 1))
    except PermissionError:
        pass
    return items

print("Project structure (depth 2):")
structure = get_structure('/app', max_depth=2)
for line in structure[:50]:
    print(line)

# Check for key packages mentioned in the task
key_paths = [
    '/app/pkg/streaming',
    '/app/pkg/endpoint',
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep',
    '/app/client',
    '/app/transport',
    '/app/pkg/remote/codec/thrift',
    '/app/pkg/remote/trans/nphttp2'
]

print("\n\nKey package existence:")
for path in key_paths:
    exists = os.path.exists(path)
    print(f"{path}: {'EXISTS' if exists else 'MISSING'}")
