
import subprocess
result = subprocess.run(
    ['grep', '-n', 'readFrameHeader\|readAndCheckFrameHeader', '/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go'],
    capture_output=True, text=True
)
print(result.stdout)
