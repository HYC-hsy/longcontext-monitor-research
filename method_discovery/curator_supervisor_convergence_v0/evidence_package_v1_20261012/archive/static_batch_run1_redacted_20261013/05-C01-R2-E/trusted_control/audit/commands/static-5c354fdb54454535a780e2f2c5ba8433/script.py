
import os
import glob

# Get the workspace directory structure
workspace_dir = r"E:\fyne_evidence_static_batch_20261012_run1\05-C01-R2-E\app"
files = []
for root, dirs, filenames in os.walk(workspace_dir):
    for filename in filenames:
        if filename.endswith('.go') or filename.endswith('.mod'):
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, workspace_dir)
            files.append(rel_path)

files.sort()
for f in files:
    print(f)
