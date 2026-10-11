
# Check if conversion methods exist in endpoint.go
grep -n "ToMiddleware\|ToUnaryMiddleware" /app/pkg/endpoint/endpoint.go || echo "MISSING: Conversion methods not found"
