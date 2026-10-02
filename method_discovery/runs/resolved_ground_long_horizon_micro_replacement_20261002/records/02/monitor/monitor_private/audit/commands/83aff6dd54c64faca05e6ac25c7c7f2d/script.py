
import subprocess
result = subprocess.run(
    ['python', 'demo.py'],
    cwd=r"E:\runs\7db2cb1c1cfce4f0d5d7fc52\workspace",
    capture_output=True,
    text=True
)
print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
print(f"Exit code: {result.returncode}")
