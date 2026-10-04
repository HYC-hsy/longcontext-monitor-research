
import os

# Check which Target 5 files now exist
target5_files = [
    '/app/client/option_unary.go',
    '/app/client/option_stream.go',
    '/app/client/option_ttstream.go'
]

print("=== TARGET 5 FILES STATUS ===")
for f in target5_files:
    if os.path.exists(f):
        size = os.path.getsize(f)
        print(f"✓ EXISTS: {os.path.basename(f)} ({size} bytes)")
    else:
        print(f"✗ MISSING: {os.path.basename(f)}")
