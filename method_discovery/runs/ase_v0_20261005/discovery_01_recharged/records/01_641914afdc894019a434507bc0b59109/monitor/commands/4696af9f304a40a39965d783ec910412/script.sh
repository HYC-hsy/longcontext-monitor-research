
# Check Target 6 frame_reader.go status
echo "=== Target 6 frame_reader.go Status ==="
echo "Required: readAndCheckFrameHeader as Framer method with enhanced error"
grep -A10 "func.*readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go 2>/dev/null || echo "readAndCheckFrameHeader METHOD NOT FOUND - still using standalone function"
