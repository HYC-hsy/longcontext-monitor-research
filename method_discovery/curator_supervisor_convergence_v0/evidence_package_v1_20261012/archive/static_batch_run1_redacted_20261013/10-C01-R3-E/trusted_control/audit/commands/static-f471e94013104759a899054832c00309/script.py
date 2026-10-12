
import os

# Check the actual evidence structure
task_evidence = r"E:\fyne_evidence_static_batch_20261012_run1\10-C01-R3-E\task_evidence"
workspace = r"E:\fyne_evidence_static_batch_20261012_run1\10-C01-R3-E\app"

print("=== Checking task_evidence directory ===")
if os.path.exists(task_evidence):
    items = os.listdir(task_evidence)
    print(f"Contents: {items[:20]}")
else:
    print("task_evidence directory not found")

print("\n=== Checking app workspace directory ===")
if os.path.exists(workspace):
    items = os.listdir(workspace)
    print(f"Contents: {items[:20]}")
    
    # Check if it's actually empty or has subdirectories
    for root, dirs, files in os.walk(workspace):
        print(f"Root: {root}")
        print(f"Dirs: {dirs[:10]}")
        print(f"Files: {files[:10]}")
        break
else:
    print("app workspace directory not found")
