
# Verify Target 5: Check if internal/client has the required types
echo "=== Checking internal/client for option types ==="
grep -r "type UnaryOption" /app/internal/client/ 2>/dev/null || echo "UnaryOption not found"
grep -r "type StreamOption" /app/internal/client/ 2>/dev/null || echo "StreamOption not found"
grep -r "type TTHeaderStreamingOption" /app/internal/client/ 2>/dev/null || echo "TTHeaderStreamingOption not found"

echo ""
echo "=== Checking if client/option.go was modified for Target 5 requirements ==="
# Check requirement #7: retry/fallback field migration
grep -n "UnaryOptions" /app/client/option.go | head -5 || echo "No UnaryOptions references"

echo ""
echo "=== Verifying Target 6 Dump() method exists ==="
grep -n "func.*Dump" /app/pkg/remote/trans/nphttp2/conn_pool.go || echo "Dump() not found"

echo ""
echo "=== Verifying Target 6 frame error enhancement ==="
grep -n "invalid frame" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/*.go 2>/dev/null || echo "Frame error enhancement not found"
