
# Verify the conversion methods were added
grep -n "ToMiddleware\|ToUnaryMiddleware" /app/pkg/endpoint/endpoint.go || echo "MISSING: Conversion methods still not found"
