
# Check if standalone readFrameHeader still exists
grep -n "^func readFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go

# Check all readFrameHeader and readAndCheckFrameHeader calls
echo "=== Call sites ==="
grep -n "readFrameHeader\|readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -v "^func"
