
# Check the duplicate UnaryEndpoint issue in cep
echo "=== Why are UnaryEndpoint types in cep? (WRONG location per task) ==="
echo "Task specifies: UnaryEndpoint types go in pkg/endpoint/endpoint.go (base package)"
echo "cep is for CLIENT-SPECIFIC STREAM endpoints only"
echo ""
grep -B 2 -A 2 "type UnaryEndpoint" /app/pkg/endpoint/cep/client_endpoint.go | head -15
