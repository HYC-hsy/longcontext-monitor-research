
# Search for all types that implement the App interface
# Looking for types with methods like New(), NewWithID(), Settings(), etc.

import subprocess
import re

# Search for App interface definition first
result = subprocess.run(
    ['grep', '-n', 'type App interface', '/app/app.go'],
    capture_output=True, text=True
)
print("=== App interface definition ===")
print(result.stdout)

# Search for all structs that might implement App
result = subprocess.run(
    ['grep', '-rn', '--include=*.go', 'type.*struct.*{', '/app/app/'],
    capture_output=True, text=True
)
print("\n=== Structs in app/ package ===")
print(result.stdout[:2000])

# Search for types implementing app-like methods
result = subprocess.run(
    ['grep', '-rn', '--include=*.go', 'func.*Metadata()', '/app/'],
    capture_output=True, text=True
)
print("\n=== Existing Metadata() methods ===")
print(result.stdout if result.stdout else "None found")
