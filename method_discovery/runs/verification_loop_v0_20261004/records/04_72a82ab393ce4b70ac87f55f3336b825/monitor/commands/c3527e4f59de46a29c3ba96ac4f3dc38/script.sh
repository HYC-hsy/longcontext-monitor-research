
# Check progress on Target 2, Target 5, and Target 6
cd /app

echo "=== TARGET 2 Progress Check ==="
echo "deprecated.go exists:"
ls -la pkg/endpoint/deprecated.go 2>/dev/null && echo "✓ Found" || echo "✗ Missing"

echo ""
echo "UnaryEndpoint in base endpoint:"
grep -c "type UnaryEndpoint" pkg/endpoint/endpoint.go && echo "✓ Found" || echo "✗ Missing"

echo ""
echo "cep package - checking for full implementation:"
wc -l pkg/endpoint/cep/endpoint.go
grep -E "StreamRecvEndpoint|StreamSendEndpoint|StreamMiddleware|DummyDummy" pkg/endpoint/cep/endpoint.go | head -10

echo ""
echo "sep package - checking for full implementation:"
wc -l pkg/endpoint/sep/endpoint.go
grep -E "StreamRecvEndpoint|StreamSendEndpoint|StreamMiddleware" pkg/endpoint/sep/endpoint.go | head -10

echo ""
echo "=== TARGET 5 Progress Check ==="
ls -la client/option_unary.go client/option_stream.go client/option_ttstream.go 2>/dev/null || echo "✗ Still missing option files"

echo ""
echo "=== TARGET 6 Progress Check ==="
grep -n "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go || echo "✗ Still missing readAndCheckFrameHeader"
