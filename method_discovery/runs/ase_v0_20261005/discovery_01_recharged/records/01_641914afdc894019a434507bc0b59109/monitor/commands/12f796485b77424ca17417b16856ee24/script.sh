
# Check Target 6 frame_reader implementation details
echo "=== TARGET 6 FRAME_READER DETAILED CHECK ==="
echo ""
echo "Required per spec:"
echo "  1. Replace standalone readFrameHeader(r) with Framer method readAndCheckFrameHeader()"
echo "  2. Enhanced error with hex dump format"
echo ""

echo "Current implementation:"
echo ""
echo "1. Method signature check:"
grep -A2 "func.*readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go 2>/dev/null || echo "  Method NOT FOUND"

echo ""
echo "2. Enhanced error format check (looking for hex dump):"
grep "invalid frame.*first4Bytes.*%#x" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go 2>/dev/null || echo "  Enhanced error format NOT FOUND"

echo ""
echo "3. Check if standalone readFrameHeader still exists:"
grep -n "^func readFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go 2>/dev/null && echo "  WARNING: Standalone function still exists" || echo "  Standalone function removed/converted"
