
# Check for DummyDummyMiddleware (double Dummy) in cep
grep -n "DummyDummyMiddleware" /app/pkg/endpoint/cep/endpoint.go || echo "NOT FOUND"
