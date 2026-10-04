
# Find where Protocol type is likely defined
import subprocess
result = subprocess.run(
    ['grep', '-r', 'type Protocol', '/app', '--include=*.go'],
    capture_output=True, text=True
)
print(result.stdout[:2000])
