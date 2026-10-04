
# Comprehensive verification of all 6 targets
cd /app

echo "=== TARGET 1: Streaming Types ==="
grep -c "type ClientStream interface" pkg/streaming/types.go && echo "✓ ClientStream exists"
grep -c "type ServerStream interface" pkg/streaming/types.go && echo "✓ ServerStream exists"
grep -c "ServerStream ServerStream" pkg/streaming/streaming.go && echo "✓ Args/Result extended"

echo ""
echo "=== TARGET 2: Endpoint Architecture ==="
ls pkg/endpoint/deprecated.go pkg/endpoint/cep/endpoint.go pkg/endpoint/sep/endpoint.go 2>/dev/null | wc -l
grep -c "DummyDummyMiddleware" pkg/endpoint/cep/endpoint.go && echo "✓ DummyDummyMiddleware exists"
grep -c "type UnaryEndpoint" pkg/endpoint/endpoint.go && echo "✓ UnaryEndpoint exists"

echo ""
echo "=== TARGET 3: Transport Protocol ==="
grep "TTHeaderStreaming Protocol = 64" transport/keys.go && echo "✓ TTHeaderStreaming = 64"
grep "GRPCStreaming Protocol = 128" transport/keys.go && echo "✓ GRPCStreaming = 128"
echo "String() method - checking for composite handling:"
grep -A30 "func (tp Protocol) String()" transport/keys.go | grep -E "default|for.*bits|&.*=.*0" && echo "✓ Has composite logic" || echo "⚠ Only handles individual flags"

echo ""
echo "=== TARGET 4: Thrift Codec ==="
grep -c "fallback.*FastCodec\|Frugal" pkg/remote/codec/thrift/thrift_data.go && echo "✓ Fallback logic exists"

echo ""
echo "=== TARGET 5: Client Options ==="
ls client/option_unary.go client/option_stream.go client/option_ttstream.go client/callopt/streamcall/streamcall.go 2>/dev/null | wc -l
grep -c "func TailOption" client/option.go && echo "✓ TailOption exists"
echo "Retry migration check:"
grep -A8 "func WithFailureRetry" client/option.go | grep "UnaryOptions.RetryMethodPolicies" && echo "✓ Migrated to UnaryOptions" || echo "⚠ Still using old location"

echo ""
echo "=== TARGET 6: gRPC Diagnostics ==="
grep -c "func (p \*connPool) Dump()" pkg/remote/trans/nphttp2/conn_pool.go && echo "✓ Dump() exists"
grep -c "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "✓ readAndCheckFrameHeader exists" || echo "✗ Missing readAndCheckFrameHeader"
grep -c "^func readFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "⚠ Standalone readFrameHeader still exists" || echo "✓ Standalone removed"
