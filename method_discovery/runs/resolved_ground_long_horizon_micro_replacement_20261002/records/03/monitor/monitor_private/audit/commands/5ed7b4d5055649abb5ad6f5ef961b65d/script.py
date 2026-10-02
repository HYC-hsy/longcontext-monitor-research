
import subprocess
result = subprocess.run(
    ['python', 'demo.py'],
    cwd='E:\\runs\\5fd794fa34dac4121b7532dd\\workspace',
    capture_output=True,
    text=True
)
print("Exit code:", result.returncode)
print("STDOUT:")
print(result.stdout)
if result.stderr:
    print("STDERR:")
    print(result.stderr)
