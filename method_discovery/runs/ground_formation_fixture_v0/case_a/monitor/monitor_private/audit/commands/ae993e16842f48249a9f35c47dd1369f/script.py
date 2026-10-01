
import subprocess
result = subprocess.run(
    ["python", "demo.py"],
    cwd=r"E:\lc_seed_sessions_20261002\s01\workspace",
    capture_output=True,
    text=True
)
print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print("Return code:", result.returncode)
