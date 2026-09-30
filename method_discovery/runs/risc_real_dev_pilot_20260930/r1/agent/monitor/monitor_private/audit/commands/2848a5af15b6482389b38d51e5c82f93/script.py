
import subprocess
import os

# Search for all App interface implementations
# Look for "var _ fyne.App = " pattern which declares conformity
result = subprocess.run(
    ["grep", "-rn", "var.*fyne.App.*=", "/app", "--include=*.go"],
    capture_output=True,
    text=True
)

print("=== App interface conformity declarations ===")
print(result.stdout)

# Also search for type definitions that might implement App
result2 = subprocess.run(
    ["grep", "-rn", "type.*struct.*{", "/app/app/", "--include=*.go"],
    capture_output=True,
    text=True
)

print("\n=== Struct types in app/ package ===")
print(result2.stdout)
