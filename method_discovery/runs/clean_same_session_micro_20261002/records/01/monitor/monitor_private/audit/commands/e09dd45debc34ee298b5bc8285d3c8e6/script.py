
import os
import subprocess

workspace_path = r"E:\runs\0d1eea45b928a84ddc072207\workspace"
demo_path = os.path.join(workspace_path, "demo.py")

# Run the demo
result = subprocess.run(
    ["python", demo_path],
    cwd=workspace_path,
    capture_output=True,
    text=True,
    timeout=5
)

print("Exit code:", result.returncode)
print("\nStdout:")
print(result.stdout)
if result.stderr:
    print("\nStderr:")
    print(result.stderr)
