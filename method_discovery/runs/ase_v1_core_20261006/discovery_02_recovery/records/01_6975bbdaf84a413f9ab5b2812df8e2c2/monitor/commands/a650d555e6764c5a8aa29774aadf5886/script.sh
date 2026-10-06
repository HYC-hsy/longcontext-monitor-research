
# Check if Target 2 requirements are met in CEP
cd /app && echo "=== CEP Package Check ==="
echo "StreamEndpoint signature (should return ClientStream):"
grep "type StreamEndpoint" pkg/endpoint/cep/endpoint.go || echo "NOT FOUND"
echo ""
echo "StreamRecvEndpoint with EqualsTo:"
grep -A1 "type StreamRecvEndpoint" pkg/endpoint/cep/endpoint.go || echo "NOT FOUND"
echo ""
echo "DummyDummyMiddleware:"
grep "DummyDummy" pkg/endpoint/cep/endpoint.go || echo "NOT FOUND"
