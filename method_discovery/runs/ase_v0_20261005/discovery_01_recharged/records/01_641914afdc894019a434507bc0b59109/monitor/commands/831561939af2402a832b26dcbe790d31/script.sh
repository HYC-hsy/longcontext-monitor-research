
# Check Target 6 status
echo "=== Target 6 Status Check ==="
echo "1. conn_pool.go Dump() method:"
grep -A5 "func.*Dump.*interface" /app/pkg/remote/trans/nphttp2/conn_pool.go | head -6 || echo "NOT FOUND"
echo ""
echo "2. frame_reader.go readAndCheckFrameHeader() method:"
grep -n "readAndCheckFrameHeader\|readFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -5 || echo "NOT FOUND"
