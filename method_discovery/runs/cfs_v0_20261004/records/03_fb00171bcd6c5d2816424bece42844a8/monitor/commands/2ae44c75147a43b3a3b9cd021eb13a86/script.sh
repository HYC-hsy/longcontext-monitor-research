
# Check for EqualsTo methods in cep package
grep -n "EqualsTo" /app/pkg/endpoint/cep/*.go 2>/dev/null | head -10

# Check for DummyDummyMiddleware in cep package  
grep -n "DummyDummyMiddleware" /app/pkg/endpoint/cep/*.go 2>/dev/null | head -5
