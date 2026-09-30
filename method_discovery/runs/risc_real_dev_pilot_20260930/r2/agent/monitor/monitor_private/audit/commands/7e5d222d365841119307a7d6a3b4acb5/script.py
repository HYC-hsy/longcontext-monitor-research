
import os

# Check what option files were created
client_path = '/app/client'
if os.path.exists(client_path):
    files = [f for f in os.listdir(client_path) if f.startswith('option_') and f.endswith('.go')]
    print("Option files in client/:")
    for f in sorted(files):
        print(f"  - {f}")
        
# Check if callopt package exists
callopt_path = '/app/client/callopt'
if os.path.exists(callopt_path):
    print("\ncallopt package exists")
    files = [f for f in os.listdir(callopt_path) if f.endswith('.go')]
    print(f"Files: {sorted(files)}")
else:
    print("\ncallopt package not found")
    
# Check for streamcall subpackage
streamcall_path = '/app/client/callopt/streamcall'
if os.path.exists(streamcall_path):
    print("\nstreamcall package exists")
    files = [f for f in os.listdir(streamcall_path) if f.endswith('.go')]
    print(f"Files: {sorted(files)}")
else:
    print("\nstreamcall package not found")
