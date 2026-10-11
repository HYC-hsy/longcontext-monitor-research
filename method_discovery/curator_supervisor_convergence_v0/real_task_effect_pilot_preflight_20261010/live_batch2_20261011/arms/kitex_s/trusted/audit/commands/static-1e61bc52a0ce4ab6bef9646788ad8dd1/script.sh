
# Check Target 2 requirement 3 - UnaryEndpoint type and conversion methods
echo "=== Target 2 Req 3: UnaryEndpoint type definition ==="
grep -n "type UnaryEndpoint\|func.*ToMiddleware\|func.*ToUnaryMiddleware" /app/pkg/endpoint/*.go
echo "---"
# Check if UnaryEndpoint type exists at all
grep -n "UnaryEndpoint" /app/pkg/endpoint/endpoint.go | head -5
