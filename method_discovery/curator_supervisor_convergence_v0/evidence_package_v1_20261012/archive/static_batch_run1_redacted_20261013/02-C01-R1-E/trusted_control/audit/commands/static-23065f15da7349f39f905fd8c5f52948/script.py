
import os
import pathlib

# Check what's in the app directory
workspace_path = pathlib.Path("E:/fyne_evidence_static_batch_20261012_run1/02-C01-R1-E/app")
print(f"Workspace path exists: {workspace_path.exists()}")
print(f"Is directory: {workspace_path.is_dir()}")

if workspace_path.exists():
    items = list(workspace_path.iterdir())
    print(f"\nItems in workspace: {len(items)}")
    for item in items[:20]:
        print(f"  {item.name} ({'dir' if item.is_dir() else 'file'})")

# Check task evidence directory
task_evidence = pathlib.Path("E:/fyne_evidence_static_batch_20261012_run1/02-C01-R1-E/task_evidence")
print(f"\n\nTask evidence path exists: {task_evidence.exists()}")
if task_evidence.exists():
    items = list(task_evidence.iterdir())
    print(f"Items in task_evidence: {len(items)}")
    for item in sorted(items)[:30]:
        print(f"  {item.name}")
