
# Check if deprecated.go exists and if UnaryEndpoint types are in place
ls -la /app/pkg/endpoint/deprecated.go 2>/dev/null || echo "deprecated.go not found"
echo "---"
ls -la /app/pkg/endpoint/unary_endpoint.go 2>/dev/null || echo "unary_endpoint.go found"
