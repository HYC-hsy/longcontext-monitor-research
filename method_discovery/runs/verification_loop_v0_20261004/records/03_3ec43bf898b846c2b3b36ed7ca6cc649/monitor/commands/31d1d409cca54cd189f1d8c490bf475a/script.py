
import os

# Check what option files were created
client_dir = "/app/client"
option_files = [f for f in os.listdir(client_dir) if f.startswith('option_') and f.endswith('.go')]
print("Created option files:")
for f in sorted(option_files):
    print(f"  {f}")
