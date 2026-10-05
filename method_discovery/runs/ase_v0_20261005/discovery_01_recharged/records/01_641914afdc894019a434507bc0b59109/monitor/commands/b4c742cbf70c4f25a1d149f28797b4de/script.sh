
# Check if the duplicate type declarations issue is real
echo "=== Checking for duplicate RecvEndpoint/SendEndpoint declarations ==="
echo "In pkg/endpoint/recv_endpoint.go:"
grep -n "^type RecvEndpoint\|^type RecvMiddleware" /app/pkg/endpoint/recv_endpoint.go 2>/dev/null | head -5 || echo "File doesn't exist or no types found"
echo ""
echo "In pkg/endpoint/send_endpoint.go:"
grep -n "^type SendEndpoint\|^type SendMiddleware" /app/pkg/endpoint/send_endpoint.go 2>/dev/null | head -5 || echo "File doesn't exist or no types found"
echo ""
echo "In pkg/endpoint/deprecated.go:"
grep -n "^type RecvEndpoint\|^type SendEndpoint" /app/pkg/endpoint/deprecated.go | head -5
