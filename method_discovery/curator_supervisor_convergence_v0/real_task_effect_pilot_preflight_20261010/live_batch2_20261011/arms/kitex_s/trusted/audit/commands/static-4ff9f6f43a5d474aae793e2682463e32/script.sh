
# Check Target 2 - UnaryEndpoint conversion methods (ToMiddleware, ToUnaryMiddleware)
echo "=== Target 2 Req 3: UnaryEndpoint conversion methods ==="
grep -n "ToMiddleware\|ToUnaryMiddleware" /app/pkg/endpoint/*.go | head -10
