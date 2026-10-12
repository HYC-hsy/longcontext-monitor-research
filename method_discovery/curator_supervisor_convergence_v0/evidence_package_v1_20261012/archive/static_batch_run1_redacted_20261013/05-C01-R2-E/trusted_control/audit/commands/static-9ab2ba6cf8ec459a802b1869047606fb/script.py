
import os
# List Go files in workspace
workspace = r"E:\fyne_evidence_static_batch_20261012_run1\05-C01-R2-E\app"
go_files = []
for root, dirs, files in os.walk(workspace):
    # Skip hidden and vendor directories
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'vendor']
    for f in files:
        if f.endswith('.go'):
            rel = os.path.relpath(os.path.join(root, f), workspace)
            go_files.append(rel)
go_files.sort()
print("\n".join(go_files[:50]))  # First 50 files
