
# Verify Target 6 Req 2: readAndCheckFrameHeader with EXACT error format
echo "=== Target 6 Req 2: Check error format requirement ==="
echo "Required: ErrFrameTooLarge AND 'invalid frame' AND 'first4Bytes=%#x, second4Bytes=%#x'"
grep -A 3 "ErrFrameTooLarge" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -E "first4Bytes.*second4Bytes|invalid frame"
echo ""
echo "=== Checking if it's a Framer method (not standalone function) ==="
grep -n "func.*readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -3
