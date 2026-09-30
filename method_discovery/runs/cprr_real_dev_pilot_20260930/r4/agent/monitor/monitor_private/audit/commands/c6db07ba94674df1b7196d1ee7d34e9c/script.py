
import os
import subprocess

# Search for Protocol type definition
result = subprocess.run(
    ['grep', '-r', 'type Protocol', '/app', '--include=*.go'],
    capture_output=True, text=True
)
print("=== type Protocol definitions ===")
print(result.stdout)

# Also search for TTHeader constant
result2 = subprocess.run(
    ['grep', '-r', 'TTHeader.*Protocol', '/app', '--include=*.go'],
    capture_output=True, text=True
)
print("\n=== TTHeader Protocol references ===")
print(result2.stdout[:2000])
