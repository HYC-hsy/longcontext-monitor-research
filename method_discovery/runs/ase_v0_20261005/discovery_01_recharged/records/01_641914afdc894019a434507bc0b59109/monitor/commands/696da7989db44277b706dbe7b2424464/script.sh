
# Critical verification of Target 5 function count
echo "=== CRITICAL: TARGET 5 FUNCTION COUNT ==="
echo ""
echo "Spec requires 8 functions in option_stream.go (excluding WithTailOption):"
echo "  1. WithStreamOptions"
echo "  2. WithStreamRecvTimeout"
echo "  3. WithStreamMiddleware"
echo "  4. WithStreamMiddlewareBuilder"
echo "  5. WithStreamRecvMiddleware"
echo "  6. WithStreamRecvMiddlewareBuilder"
echo "  7. WithStreamSendMiddleware"
echo "  8. WithStreamSendMiddlewareBuilder"
echo ""
echo "Current functions:"
grep "^func WithStream" /app/client/option_stream.go
echo ""
echo "Count (excluding WithTailOption):"
grep "^func WithStream" /app/client/option_stream.go | wc -l
echo ""
echo "Expected: 8"
