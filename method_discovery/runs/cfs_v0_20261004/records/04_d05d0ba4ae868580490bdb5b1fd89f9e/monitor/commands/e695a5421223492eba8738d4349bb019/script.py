
import os
import subprocess

# Check what files were created for Target 5
result = subprocess.run(
    ['find', '/app/client', '-type', 'f', '-name', '*.go', '-newer', '/app/go.mod'],
    capture_output=True,
    text=True
)

print("=== NEW FILES IN CLIENT PACKAGE ===")
print(result.stdout if result.stdout else "None")

# Check specifically for the required files
required_files = [
    '/app/client/option_unary.go',
    '/app/client/option_stream.go', 
    '/app/client/option_ttstream.go',
    '/app/client/option_categories.go'
]

print("\n=== CHECKING REQUIRED FILES ===")
for f in required_files:
    exists = "✓ EXISTS" if os.path.exists(f) else "✗ MISSING"
    print(f"{exists}: {os.path.basename(f)}")

# Check for default protocol setting
print("\n=== SEARCHING FOR DEFAULT TRANSPORT PROTOCOL ===")
result2 = subprocess.run(
    ['grep', '-r', 'Framed', '/app/client/', '--include=*.go', '-n'],
    capture_output=True,
    text=True
)
print("References to 'Framed' in client package:")
print(result2.stdout[:1000] if result2.stdout else "None found")
