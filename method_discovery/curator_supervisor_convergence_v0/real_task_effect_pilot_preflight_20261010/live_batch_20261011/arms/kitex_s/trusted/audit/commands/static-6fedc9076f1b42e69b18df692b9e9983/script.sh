cd /app

echo "=== TARGET 1: Streaming Types ==="
echo "Checking pkg/streaming for required interfaces..."
grep -n "type ClientStream interface\|type ServerStream interface\|type Header\|type Trailer" pkg/streaming/*.go | head -20

echo ""
echo "Checking for generic wrapper functions..."
grep -n "func NewServerStreamingClient\|func NewBidiStreamingClient\|func NewClientStreamingClient" pkg/streaming/*.go | head -10

echo ""
echo "=== TARGET 2: Endpoint Packages ==="
ls -la pkg/endpoint/cep/ 2>/dev/null && echo "✓ cep exists" || echo "✗ cep missing"
ls -la pkg/endpoint/sep/ 2>/dev/null && echo "✓ sep exists" || echo "✗ sep missing"

echo ""
echo "Checking for UnaryEndpoint and conversion methods..."
grep -n "type UnaryEndpoint\|ToMiddleware\|ToUnaryMiddleware" pkg/endpoint/endpoint.go | head -10
