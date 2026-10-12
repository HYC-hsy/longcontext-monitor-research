
import os

# Use the correct workspace path from the environment
workspace_base = os.environ.get('task_workspace_', 'task/workspace/')
print(f"Workspace base: {workspace_base}")
print(f"Checking if path exists: {os.path.exists(workspace_base)}")

# List what's in the workspace
if os.path.exists(workspace_base):
    print(f"\nContents of {workspace_base}:")
    print(os.listdir(workspace_base)[:20])
