
# Check for EqualsTo methods in cep package
grep -n "EqualsTo" /app/pkg/endpoint/cep/endpoint.go || echo "EqualsTo not found in cep"
echo "---"
# Check for DummyDummyMiddleware (note double Dummy)
grep -n "DummyDummyMiddleware" /app/pkg/endpoint/cep/endpoint.go || echo "DummyDummyMiddleware not found in cep"
