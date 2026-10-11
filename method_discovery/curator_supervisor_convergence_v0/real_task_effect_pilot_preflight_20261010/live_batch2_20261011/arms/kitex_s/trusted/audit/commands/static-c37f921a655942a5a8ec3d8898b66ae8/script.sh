
# Check current state of UnaryEndpoint and conversion methods
echo "=== Check if UnaryEndpoint types exist in pkg/endpoint/endpoint.go ==="
grep -n "UnaryEndpoint\|UnaryMiddleware" /app/pkg/endpoint/endpoint.go | head -10
echo "---"
echo "=== Check what's in cep that's causing the error ==="
grep -n "func.*ToMiddleware\|func.*ToUnaryMiddleware" /app/pkg/endpoint/cep/client_endpoint.go
