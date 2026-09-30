
import os

# List files in streaming package
streaming_path = '/app/pkg/streaming'
if os.path.exists(streaming_path):
    files = sorted(os.listdir(streaming_path))
    print("Files in pkg/streaming:")
    for f in files:
        print(f"  {f}")
        
# Check if key files exist
key_files = [
    '/app/pkg/streaming/stream.go',
    '/app/pkg/endpoint/cep/stream.go',
    '/app/pkg/endpoint/sep/stream.go',
    '/app/pkg/endpoint/deprecated.go',
    '/app/client/option_unary.go',
    '/app/client/option_stream.go',
    '/app/client/option_ttstream.go',
    '/app/transport/protocol.go',
]

print("\n\nKey file existence:")
for f in key_files:
    exists = os.path.exists(f)
    print(f"{f}: {'EXISTS' if exists else 'MISSING'}")
