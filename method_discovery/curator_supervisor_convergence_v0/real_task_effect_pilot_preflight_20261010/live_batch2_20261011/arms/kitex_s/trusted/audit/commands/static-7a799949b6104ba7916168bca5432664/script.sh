
# Check if UnaryEndpoint is duplicated in wrong location (cep)
echo "=== Target 2: UnaryEndpoint should ONLY be in endpoint.go, NOT in cep ==="
echo ""
echo "In endpoint.go (CORRECT):"
grep -n "type UnaryEndpoint" /app/pkg/endpoint/endpoint.go
echo ""
echo "In cep/client_endpoint.go (WRONG - should NOT exist here):"
grep -n "type UnaryEndpoint" /app/pkg/endpoint/cep/client_endpoint.go
echo ""
echo "Task states: cep is for CLIENT-SPECIFIC STREAM endpoints, not unary"
