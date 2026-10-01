
# Verify all required files exist for all 6 targets
echo "=== Target 1: Streaming Types ==="
test -f /app/pkg/streaming/stream_types.go && echo "✓ stream_types.go exists" || echo "✗ MISSING"
grep -q "type ClientStream interface" /app/pkg/streaming/stream_types.go && echo "✓ ClientStream defined" || echo "✗ MISSING"
grep -q "type ServerStream interface" /app/pkg/streaming/stream_types.go && echo "✓ ServerStream defined" || echo "✗ MISSING"
grep -q "NewBidiStreamingClient" /app/pkg/streaming/stream_types.go && echo "✓ Generic factories exist" || echo "✗ MISSING"

echo ""
echo "=== Target 2: Endpoint Packages ==="
test -d /app/pkg/endpoint/cep && echo "✓ cep package exists" || echo "✗ MISSING"
test -d /app/pkg/endpoint/sep && echo "✓ sep package exists" || echo "✗ MISSING"
test -f /app/pkg/endpoint/deprecated.go && echo "✓ deprecated.go exists" || echo "✗ MISSING"
grep -q "type UnaryEndpoint Endpoint" /app/pkg/endpoint/endpoint.go && echo "✓ UnaryEndpoint as named type" || echo "✗ MISSING"

echo ""
echo "=== Target 3: Transport Protocol ==="
grep "TTHeaderStreaming.*64" /app/transport/keys.go && echo "✓ TTHeaderStreaming=64"
grep "GRPCStreaming.*128" /app/transport/keys.go && echo "✓ GRPCStreaming=128"

echo ""
echo "=== Target 5: Client Options ==="
test -f /app/client/option_unary.go && echo "✓ option_unary.go exists" || echo "✗ MISSING"
test -f /app/client/option_stream.go && echo "✓ option_stream.go exists" || echo "✗ MISSING"
test -f /app/client/option_ttstream.go && echo "✓ option_ttstream.go exists" || echo "✗ MISSING"

echo ""
echo "=== Target 6: gRPC Diagnostics ==="
grep -q "func.*Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go && echo "✓ Dump() method exists" || echo "✗ MISSING"
grep -q "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "✓ readAndCheckFrameHeader exists" || echo "✗ MISSING"
