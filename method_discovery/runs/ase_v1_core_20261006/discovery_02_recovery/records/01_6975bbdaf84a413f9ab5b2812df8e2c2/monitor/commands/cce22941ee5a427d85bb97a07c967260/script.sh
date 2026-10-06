
# Check deprecated.go for RecvEndpoint/SendEndpoint
cd /app && echo "=== Deprecated endpoint types ==="
grep -E "type (Recv|Send)Endpoint|RecvMiddleware|SendMiddleware" pkg/endpoint/deprecated.go || echo "NOT FOUND"
