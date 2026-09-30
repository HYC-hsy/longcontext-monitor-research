
# Check Target 6 implementation
import subprocess

# Find readAndCheckFrameHeader
result = subprocess.run(['grep', '-n', 'readAndCheckFrameHeader', 
                        '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
                       capture_output=True, text=True)
print("=== readAndCheckFrameHeader in frame_reader.go ===")
print(result.stdout if result.stdout else "Not found")

# Check for Dump method in conn_pool
result2 = subprocess.run(['grep', '-n', 'func.*Dump', 
                         '/app/pkg/remote/trans/nphttp2/conn_pool.go'],
                        capture_output=True, text=True)
print("\n=== Dump method in conn_pool.go ===")
print(result2.stdout if result2.stdout else "Not found")
