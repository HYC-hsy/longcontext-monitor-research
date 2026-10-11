
# Search for readAndCheckFrameHeader or readFrameHeader in frame_reader.go
echo "=== Searching for frame header reading functions ==="
grep -n "readFrameHeader\|readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -10
