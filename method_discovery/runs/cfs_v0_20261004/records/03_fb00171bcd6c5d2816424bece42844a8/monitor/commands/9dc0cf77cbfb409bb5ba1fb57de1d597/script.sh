
# Verify EqualsTo methods exist in cep
grep -n "func.*EqualsTo" /app/pkg/endpoint/cep/endpoint.go | head -5

# Verify DummyDummyMiddleware exists in cep
grep -n "DummyDummyMiddleware" /app/pkg/endpoint/cep/endpoint.go | head -3

# Verify EqualsTo methods exist in sep
grep -n "func.*EqualsTo" /app/pkg/endpoint/sep/endpoint.go | head -5
