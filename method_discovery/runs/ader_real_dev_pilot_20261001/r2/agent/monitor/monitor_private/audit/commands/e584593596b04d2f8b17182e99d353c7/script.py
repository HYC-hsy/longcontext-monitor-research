
import os

# Find transport protocol files
transport_path = '/app/transport'
if os.path.exists(transport_path):
    files = sorted([f for f in os.listdir(transport_path) if f.endswith('.go')])
    print("Files in transport/:")
    for f in files:
        print(f"  {f}")
        
# Find client option files
client_path = '/app/client'
if os.path.exists(client_path):
    files = sorted([f for f in os.listdir(client_path) if f.endswith('.go')])
    print("\n\nFiles in client/:")
    for f in files:
        print(f"  {f}")
        
# Find endpoint files
endpoint_path = '/app/pkg/endpoint'
if os.path.exists(endpoint_path):
    files = sorted([f for f in os.listdir(endpoint_path) if f.endswith('.go')])
    print("\n\nFiles in pkg/endpoint/:")
    for f in files:
        print(f"  {f}")
