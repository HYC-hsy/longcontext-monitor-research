
import os
import json

workspace_path = r"E:\runs\0d1eea45b928a84ddc072207\workspace"

# List all files in the workspace
for root, dirs, files in os.walk(workspace_path):
    level = root.replace(workspace_path, '').count(os.sep)
    indent = ' ' * 2 * level
    rel_root = os.path.relpath(root, workspace_path)
    if rel_root == '.':
        print('workspace/')
    else:
        print(f'{indent}{os.path.basename(root)}/')
    subindent = ' ' * 2 * (level + 1)
    for file in sorted(files):
        print(f'{subindent}{file}')
