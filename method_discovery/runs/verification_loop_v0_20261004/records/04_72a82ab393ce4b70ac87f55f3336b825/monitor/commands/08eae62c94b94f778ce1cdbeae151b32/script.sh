
# Check for deprecated.go and UnaryEndpoint in pkg/endpoint
cd /app
ls -la pkg/endpoint/deprecated.go 2>/dev/null || echo "deprecated.go not found"
grep -n "type UnaryEndpoint" pkg/endpoint/endpoint.go 2>/dev/null || echo "UnaryEndpoint not found in endpoint.go"
