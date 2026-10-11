
# Look for all potential App interface implementations
# Search for methods that are part of App interface

import subprocess

# First, let's see what methods App interface requires
result = subprocess.run(
    ['grep', '-A', '20', 'type App interface', '/app/app.go'],
    capture_output=True, text=True
)
print("=== App interface methods ===")
print(result.stdout)

# Search for types that might implement App - look for NewWithID methods
result = subprocess.run(
    ['grep', '-rn', '--include=*.go', 'func.*NewWithID', '/app/'],
    capture_output=True, text=True
)
print("\n=== NewWithID implementations ===")
print(result.stdout)

# Look for test implementations
result = subprocess.run(
    ['grep', '-rn', '--include=*_test.go', 'type.*App', '/app/app/'],
    capture_output=True, text=True
)
print("\n=== Test App types ===")
print(result.stdout if result.stdout else "None found")
