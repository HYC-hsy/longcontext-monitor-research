
# Check the remaining work for Target 5 and Target 6
cd /app

echo "=== TARGET 5: Retry/fallback migration check ==="
echo "Checking if WithFailureRetry stores in UnaryOptions.RetryMethodPolicies:"
grep -A10 "func WithFailureRetry" client/option.go | grep -E "UnaryOptions|RetryMethodPolicies" || echo "✗ Not yet migrated"

echo ""
echo "=== TARGET 6: Final check ==="
echo "readAndCheckFrameHeader method:"
grep -c "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "✓ Implemented" || echo "✗ Still missing"

echo ""
echo "readFrameHeader standalone (should be removed or refactored):"
grep -n "^func readFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "⚠ Still exists as standalone" || echo "✓ Removed or refactored"

echo ""
echo "=== String() method for composite protocols (Target 3) ==="
grep -A30 "func (tp Protocol) String()" transport/keys.go | tail -20
