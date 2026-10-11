
# Check the exact error format in frame_reader.go for Target 6
echo "=== Target 6: Checking EXACT error format requirement ==="
echo "Task requires: ErrFrameTooLarge + 'invalid frame' + first4Bytes=%#x + second4Bytes=%#x"
echo ""
grep -A 15 "func.*readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -E "Errorf|ErrFrameTooLarge|invalid frame|second4Bytes"
