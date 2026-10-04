
import os
import glob

# Check what exists in key packages
streaming_files = glob.glob('/app/pkg/streaming/*.go')
endpoint_files = glob.glob('/app/pkg/endpoint/*.go')
transport_files = glob.glob('/app/transport/*.go')

print("Streaming package files:")
for f in sorted(streaming_files):
    print(f"  {os.path.basename(f)}")

print("\nEndpoint package files:")
for f in sorted(endpoint_files):
    print(f"  {os.path.basename(f)}")

print("\nTransport package files:")
for f in sorted(transport_files):
    print(f"  {os.path.basename(f)}")
