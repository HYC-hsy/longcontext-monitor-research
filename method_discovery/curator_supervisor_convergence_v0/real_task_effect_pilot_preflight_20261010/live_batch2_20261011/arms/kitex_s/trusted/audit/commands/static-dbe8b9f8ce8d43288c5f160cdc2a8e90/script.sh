
# Check if UnaryEndpoint types are in pkg/endpoint (base package) as required
echo "=== Checking if UnaryEndpoint is in pkg/endpoint/endpoint.go (REQUIRED location) ==="
grep -n "type UnaryEndpoint\|type UnaryMiddleware\|ToMiddleware\|ToUnaryMiddleware" /app/pkg/endpoint/endpoint.go | head -15
echo "---"
echo "=== Checking if they're in cep (WRONG location) ==="
grep -n "type UnaryEndpoint\|type UnaryMiddleware" /app/pkg/endpoint/cep/client_endpoint.go | head -5
