
# Find where transport protocol constants are defined
import os
import subprocess

result = subprocess.run(
    ['grep', '-r', 'type Protocol', '/app/', '--include=*.go'],
    capture_output=True,
    text=True
)
print("Protocol type definitions:")
print(result.stdout)
print("\n" + "="*60 + "\n")

result2 = subprocess.run(
    ['grep', '-r', 'const.*TTHeader', '/app/', '--include=*.go'],
    capture_output=True,
    text=True
)
print("TTHeader constants:")
print(result2.stdout[:2000])  # Limit output
