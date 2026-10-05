
# Comprehensive verification of all 6 targets
echo "=== FINAL COMPREHENSIVE VERIFICATION (Turn 221 Completion Check) ==="
echo ""

echo "TARGET 1: Streaming Types"
[ -f "/app/pkg/streaming/stream_types.go" ] && echo "  ✓ stream_types.go exists" || echo "  ✗ MISSING"

echo ""
echo "TARGET 2: Endpoint Architecture"
[ -d "/app/pkg/endpoint/cep" ] && [ -d "/app/pkg/endpoint/sep" ] && [ -f "/app/pkg/endpoint/deprecated.go" ] && echo "  ✓ All packages exist" || echo "  ✗ INCOMPLETE"

echo ""
echo "TARGET 3: Transport Protocol"
grep -q "r.transportProtocol = transport.Framed" /app/pkg/rpcinfo/rpcconfig.go && echo "  ✓ Default protocol = Framed" || echo "  ✗ Default not changed"
grep -q "TTHeaderStreaming.*64" /app/transport/keys.go && grep -q "GRPCStreaming.*128" /app/transport/keys.go && echo "  ✓ Flags correct" || echo "  ✗ Flags incorrect"

echo ""
echo "TARGET 4: Thrift Codec Fallback"
grep -q "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go && echo "  ✗ Basic exclusion PRESENT" || echo "  ✓ Basic exclusion removed"

echo ""
echo "TARGET 5: Client Options - CRITICAL CHECK"
echo "  Required: 8 functions with cep types in option_stream.go"
echo "  Current function count:"
grep -c "^func WithStream" /app/client/option_stream.go || echo "  0"
echo "  Current functions:"
grep "^func WithStream" /app/client/option_stream.go | head -8
echo ""
echo "  CRITICAL: Check if WithStreamOptions exists:"
grep -q "^func WithStreamOptions" /app/client/option_stream.go && echo "  ✓ WithStreamOptions exists" || echo "  ✗ WithStreamOptions MISSING"

echo ""
echo "TARGET 6: gRPC Diagnostics"
grep -q "func (fr \*Framer) readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "  ✓ readAndCheckFrameHeader method exists" || echo "  ✗ MISSING"
grep -q "func.*Dump.*interface" /app/pkg/remote/trans/nphttp2/conn_pool.go && echo "  ✓ Dump() method exists" || echo "  ✗ MISSING"
