
import os

# Verify Target 5 files exist
required_files = {
    "option_unary.go": "/app/client/option_unary.go",
    "option_stream.go": "/app/client/option_stream.go",
    "option_ttstream.go": "/app/client/option_ttstream.go",
    "streamcall package": "/app/client/callopt/streamcall/streamcall.go"
}

print("Target 5 Required Files Check:")
all_exist = True
for name, path in required_files.items():
    exists = os.path.exists(path)
    print(f"  {name}: {'✓' if exists else '✗ MISSING'}")
    if not exists:
        all_exist = False

print(f"\nAll required files present: {'YES' if all_exist else 'NO'}")
