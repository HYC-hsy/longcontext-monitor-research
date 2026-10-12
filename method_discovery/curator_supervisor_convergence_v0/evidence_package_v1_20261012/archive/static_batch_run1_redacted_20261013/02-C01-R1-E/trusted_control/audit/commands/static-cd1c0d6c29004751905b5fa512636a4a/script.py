
import os
import pathlib

workspace_path = pathlib.Path("E:/fyne_evidence_static_batch_20261012_run1/02-C01-R1-E/app")

# List all Go files in the workspace
go_files = []
for root, dirs, files in os.walk(workspace_path):
    for file in files:
        if file.endswith('.go'):
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, workspace_path)
            go_files.append(rel_path)

go_files.sort()
for f in go_files[:50]:  # First 50 files
    print(f)

print(f"\nTotal Go files: {len(go_files)}")
