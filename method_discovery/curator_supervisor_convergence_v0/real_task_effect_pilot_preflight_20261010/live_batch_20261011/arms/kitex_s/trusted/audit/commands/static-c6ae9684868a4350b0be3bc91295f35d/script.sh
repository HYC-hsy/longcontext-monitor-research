
# Check if Target 6 files exist
echo "=== Checking Target 6: gRPC Diagnostics ==="
echo "1. Connection pool Dump() method:"
grep -n "func.*Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go 2>/dev/null || echo "NOT FOUND"

echo ""
echo "2. Enhanced frame header validation:"
grep -n "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go 2>/dev/null || echo "NOT FOUND"
