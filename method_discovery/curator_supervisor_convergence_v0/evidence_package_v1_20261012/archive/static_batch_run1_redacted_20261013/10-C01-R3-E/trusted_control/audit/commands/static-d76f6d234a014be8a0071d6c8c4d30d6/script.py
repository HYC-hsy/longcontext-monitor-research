
import os
import json

workspace = r"E:\fyne_evidence_static_batch_20261012_run1\10-C01-R3-E\app"

# Find all Go files that were likely modified
go_files = []
for root, dirs, files in os.walk(workspace):
    # Skip vendor and hidden directories
    dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'vendor']
    for file in files:
        if file.endswith('.go'):
            rel_path = os.path.relpath(os.path.join(root, file), workspace)
            go_files.append(rel_path)

# Sort and show key files related to the targets
key_patterns = ['app.go', 'menu.go', 'container.go', 'toolbar.go', 'hyperlink.go', 
                'entry.go', 'sprintf.go', 'all.go', 'meta.go', 'json.go', 'desktop']

key_files = []
other_files = []
for f in sorted(go_files):
    if any(pattern in f.lower() for pattern in key_patterns):
        key_files.append(f)
    else:
        other_files.append(f)

print("Key implementation files found:")
for f in key_files[:30]:
    print(f"  {f}")
    
print(f"\nTotal Go files: {len(go_files)}")
