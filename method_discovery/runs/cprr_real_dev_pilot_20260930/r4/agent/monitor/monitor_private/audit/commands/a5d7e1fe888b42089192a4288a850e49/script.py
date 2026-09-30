
import subprocess
# Check for readFrameHeader and readAndCheckFrameHeader
result = subprocess.run(
    ['grep', '-n', 'func.*readFrameHeader\|func.*readAndCheckFrameHeader', '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
    capture_output=True, text=True
)
print("Function definitions:")
print(result.stdout)
