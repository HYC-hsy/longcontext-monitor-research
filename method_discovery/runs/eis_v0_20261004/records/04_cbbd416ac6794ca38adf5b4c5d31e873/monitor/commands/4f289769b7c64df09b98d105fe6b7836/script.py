
# Check if the build actually succeeded
import subprocess

result = subprocess.run(
    ['go', 'build', './pkg/streaming/'],
    cwd='/app',
    capture_output=True,
    text=True,
    timeout=30
)

print(f"Exit code: {result.exit_code}")
if result.stdout:
    print(f"Stdout:\n{result.stdout}")
if result.stderr:
    print(f"Stderr:\n{result.stderr}")
