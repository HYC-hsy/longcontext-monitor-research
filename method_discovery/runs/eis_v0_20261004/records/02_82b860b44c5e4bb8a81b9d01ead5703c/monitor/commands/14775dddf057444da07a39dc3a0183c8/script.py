
# Find all App implementations in the codebase
# Look for types that implement the App interface
import subprocess
import re

result = subprocess.run(
    ['grep', '-r', '-n', 'type.*struct', '/app', '--include=*.go'],
    capture_output=True, text=True
)

# Also look for interface implementations specifically mentioning App
app_impl_result = subprocess.run(
    ['grep', '-r', '-n', 'var.*fyne.App', '/app', '--include=*.go'],
    capture_output=True, text=True
)

# Look for test app implementations
test_app_result = subprocess.run(
    ['grep', '-r', '-n', 'testApp\\|mockApp\\|dummyApp', '/app', '--include=*.go'],
    capture_output=True, text=True
)

print("=== Potential App implementations (struct definitions) ===")
lines = result.stdout.split('\n')
for line in lines[:50]:  # First 50 to avoid too much output
    if 'app' in line.lower() or 'App' in line:
        print(line)

print("\n=== Interface conformance declarations ===")
print(app_impl_result.stdout[:2000])

print("\n=== Test/Mock App implementations ===")
print(test_app_result.stdout[:2000])
