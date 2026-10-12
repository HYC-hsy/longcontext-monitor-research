
import os
import pathlib

# Use the task/workspace path as indicated in environment
workspace_base = pathlib.Path("task/workspace")
print(f"Checking workspace_base: {workspace_base}")
print(f"Exists: {workspace_base.exists()}")

if workspace_base.exists():
    # List all Go files
    go_files = []
    for root, dirs, files in os.walk(workspace_base):
        for file in files:
            if file.endswith('.go'):
                filepath = pathlib.Path(root) / file
                rel_path = filepath.relative_to(workspace_base)
                go_files.append(str(rel_path))
    
    go_files.sort()
    print(f"\nTotal Go files found: {len(go_files)}")
    print("\nFirst 50 files:")
    for f in go_files[:50]:
        print(f"  {f}")
else:
    print("Workspace does not exist - checking what's in task/")
    task_base = pathlib.Path("task")
    if task_base.exists():
        items = list(task_base.iterdir())
        print(f"\nItems in task/: {len(items)}")
        for item in sorted(items)[:20]:
            print(f"  {item.name}")
