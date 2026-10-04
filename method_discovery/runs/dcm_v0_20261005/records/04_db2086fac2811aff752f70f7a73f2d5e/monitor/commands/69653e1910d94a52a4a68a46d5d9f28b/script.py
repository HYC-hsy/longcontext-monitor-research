
import os
import glob

# Check endpoint package for missing Target 2 items
endpoint_files = sorted(glob.glob('/app/pkg/endpoint/*.go'))
print("Endpoint package files:")
for f in endpoint_files:
    print(f"  {os.path.basename(f)}")

# Check client package for Target 5 files
client_option_files = sorted(glob.glob('/app/client/option*.go'))
print("\nClient option files:")
for f in client_option_files:
    print(f"  {os.path.basename(f)}")

# Check if streamcall package exists for Target 5
streamcall_exists = os.path.isdir('/app/client/callopt/streamcall')
print(f"\nstreamcall package exists: {streamcall_exists}")

if streamcall_exists:
    streamcall_files = sorted(glob.glob('/app/client/callopt/streamcall/*.go'))
    print("streamcall files:")
    for f in streamcall_files:
        print(f"  {os.path.basename(f)}")
