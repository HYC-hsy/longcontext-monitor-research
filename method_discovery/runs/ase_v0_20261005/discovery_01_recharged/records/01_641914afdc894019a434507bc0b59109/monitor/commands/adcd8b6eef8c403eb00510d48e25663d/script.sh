
# Check if deprecated.go is missing middleware/builder/chain types per spec
echo "=== Checking deprecated.go for required types ==="
grep -E "RecvMiddleware|SendMiddleware|RecvChain|SendChain|RecvMiddlewareBuilder|SendMiddlewareBuilder" /app/pkg/endpoint/deprecated.go || echo "MISSING middleware/builder/chain types"
