
import os

# Check what new files/directories exist
print("New directories:")
for d in ['/app/pkg/endpoint/cep', '/app/pkg/endpoint/sep']:
    if os.path.exists(d):
        print(f"{d}: EXISTS")
        files = [f for f in os.listdir(d) if f.endswith('.go')]
        for f in sorted(files):
            print(f"  - {f}")
    else:
        print(f"{d}: MISSING")

print("\n\nNew files in pkg/streaming:")
streaming_files = os.listdir('/app/pkg/streaming')
for f in sorted(streaming_files):
    if f.endswith('.go'):
        print(f"  {f}")

print("\n\nGit status to see modified files:")
import subprocess
result = subprocess.run(['git', 'status', '--porcelain'], cwd='/app', capture_output=True, text=True)
modified = [line for line in result.stdout.split('\n') if line.strip()]
for line in modified[:20]:  # First 20 changes
    print(f"  {line}")
