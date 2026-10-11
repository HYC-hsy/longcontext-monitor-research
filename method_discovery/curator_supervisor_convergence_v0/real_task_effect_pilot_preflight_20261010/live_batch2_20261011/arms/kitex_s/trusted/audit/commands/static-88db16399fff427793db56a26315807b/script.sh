
# Verify Target 2 Req 3: UnaryEndpoint types in pkg/endpoint/endpoint.go (NOT in cep)
echo "=== Target 2 Req 3: UnaryEndpoint in pkg/endpoint/endpoint.go ==="
grep -n "type UnaryEndpoint\|type UnaryMiddleware\|func.*ToMiddleware\|func.*ToUnaryMiddleware" /app/pkg/endpoint/endpoint.go | head -10
echo ""
echo "=== Should NOT be in cep (wrong location) ==="
grep -n "type UnaryEndpoint\|type UnaryMiddleware" /app/pkg/endpoint/cep/client_endpoint.go 2>/dev/null | head -5 || echo "Good: Not in cep"
