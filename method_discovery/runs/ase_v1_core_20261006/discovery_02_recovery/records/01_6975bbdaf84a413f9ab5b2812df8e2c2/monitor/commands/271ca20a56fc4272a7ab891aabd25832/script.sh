
# Check current Target 2 status
echo "=== TARGET 2 CEP CURRENT STATUS ==="
echo "StreamEndpoint signature:"
grep "type StreamEndpoint" /app/pkg/endpoint/cep/endpoint.go | head -1

echo ""
echo "StreamRecvEndpoint:"
grep "type StreamRecvEndpoint" /app/pkg/endpoint/cep/endpoint.go | head -1

echo ""
echo "DummyDummyMiddleware:"
grep "DummyDummy" /app/pkg/endpoint/cep/endpoint.go | head -1
