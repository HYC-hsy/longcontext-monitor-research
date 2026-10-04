
import subprocess
import os

# Check if any new files have been created in key locations
result = subprocess.run(
    ['find', '/app/pkg/streaming', '/app/pkg/endpoint', '/app/transport', '/app/client', 
     '-type', 'f', '-newer', '/app/go.mod'],
    capture_output=True,
    text=True
)

print("Files newer than go.mod (baseline):")
print(result.stdout if result.stdout else "None found")
print()

# Check for new directories
result2 = subprocess.run(
    ['find', '/app/pkg/endpoint', '-type', 'd'],
    capture_output=True,
    text=True
)
print("Directories in pkg/endpoint:")
print(result2.stdout)
