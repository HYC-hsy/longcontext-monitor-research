
import os

# Check for new directories
new_dirs = [
    '/app/pkg/endpoint/cep',
    '/app/pkg/endpoint/sep'
]

print("New directory check:")
for d in new_dirs:
    exists = os.path.exists(d)
    print(f"{d}: {'EXISTS' if exists else 'MISSING'}")

# Check for new files in key locations
new_files = [
    '/app/pkg/streaming/stream.go',
    '/app/pkg/endpoint/deprecated.go',
    '/app/client/option_unary.go',
    '/app/client/option_stream.go', 
    '/app/client/option_ttstream.go'
]

print("\n\nNew file check:")
for f in new_files:
    exists = os.path.exists(f)
    print(f"{f}: {'EXISTS' if exists else 'MISSING'}")

# Check if transport/keys.go has been modified
import subprocess
result = subprocess.run(
    ['git', 'status', '--porcelain', 'transport/keys.go'],
    cwd='/app',
    capture_output=True,
    text=True
)
print(f"\n\ntransport/keys.go git status: {result.stdout.strip() if result.stdout.strip() else 'UNMODIFIED'}")
