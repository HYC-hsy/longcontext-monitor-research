
# Check what was actually done for Target 4
import subprocess

# Search for thrift codec changes
result = subprocess.run(['grep', '-rn', 'IsStreamingProtocol\\|streaming protocol', 
                        '/app/pkg/protocol/bthrift/', '/app/pkg/remote/codec/thrift/'],
                       capture_output=True, text=True, timeout=5)
print("=== Streaming protocol changes ===")
print(result.stdout[:1000] if result.stdout else "Not found")

# Check for fallback logic in thrift codec
result2 = subprocess.run(['grep', '-n', 'FastCodec\\|Frugal\\|fallback', 
                         '/app/pkg/remote/codec/thrift/thrift_data.go'],
                        capture_output=True, text=True, timeout=5)
print("\n=== Fallback logic in thrift_data.go ===")
print(result2.stdout[:1000] if result2.stdout else "Not found")
