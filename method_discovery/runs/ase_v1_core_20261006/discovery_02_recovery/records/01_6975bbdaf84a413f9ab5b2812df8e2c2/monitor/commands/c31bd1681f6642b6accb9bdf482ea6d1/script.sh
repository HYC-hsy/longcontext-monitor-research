
# Check Target 6 implementations
echo "=== TARGET 6 VERIFICATION ==="
echo "1. conn_pool.go Dump() method:"
grep -A5 "func.*Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go | head -10

echo ""
echo "2. readAndCheckFrameHeader method:"
grep -A5 "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -10

echo ""
echo "3. Check if readFrameHeader was replaced:"
grep -c "func readFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
