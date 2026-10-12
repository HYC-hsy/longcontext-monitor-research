
import os
import json

# Get the workspace path
workspace = "E:\\fyne_evidence_static_batch_20261012_run1\\10-C01-R3-E\\app"

# Walk through and list all Go files
go_files = []
for root, dirs, files in os.walk(workspace):
    for file in files:
        if file.endswith('.go'):
            rel_path = os.path.relpath(os.path.join(root, file), workspace)
            go_files.append(rel_path)

# Sort and display
go_files.sort()
print(f"Total Go files: {len(go_files)}\n")
for f in go_files[:50]:  # First 50 files
    print(f)
