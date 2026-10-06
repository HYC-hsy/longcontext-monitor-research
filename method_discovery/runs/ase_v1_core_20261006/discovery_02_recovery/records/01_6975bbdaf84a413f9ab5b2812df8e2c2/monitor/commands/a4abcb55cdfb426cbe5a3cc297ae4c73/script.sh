
# Check UnaryEndpoint conversion methods in pkg/endpoint/endpoint.go
cd /app && grep -A5 "ToMiddleware\|ToUnaryMiddleware" pkg/endpoint/endpoint.go
