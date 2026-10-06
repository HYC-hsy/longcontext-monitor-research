
# Check UnaryEndpoint methods in endpoint.go
cd /app && echo "=== UnaryEndpoint conversion methods ==="
grep -E "func.*To(Unary)?Middleware|UnaryChain" pkg/endpoint/endpoint.go || echo "NOT FOUND"
