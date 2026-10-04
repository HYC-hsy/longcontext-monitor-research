
# Check if the required Target 5 files exist
import os

required_files = [
    "/app/client/option_unary.go",
    "/app/client/option_stream.go", 
    "/app/client/option_ttstream.go"
]

print("Target 5 Required Files:")
for f in required_files:
    exists = os.path.exists(f)
    print(f"  {os.path.basename(f)}: {'✓ EXISTS' if exists else '✗ MISSING'}")

print("\nActual option files created:")
client_dir = "/app/client"
if os.path.exists(client_dir):
    option_files = sorted([f for f in os.listdir(client_dir) if f.startswith('option_') and f.endswith('.go')])
    for f in option_files:
        print(f"  {f}")
