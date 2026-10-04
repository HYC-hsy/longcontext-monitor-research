
import os
import subprocess

# Find what files were created in cep and sep
result = subprocess.run(
    ['find', '/app/pkg/endpoint', '-type', 'f', '-name', '*.go'],
    capture_output=True,
    text=True
)
print("Files in pkg/endpoint:")
print(result.stdout)
