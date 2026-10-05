
# Comprehensive verification of all 6 targets (Turn 128)
echo "=== FINAL TARGET VERIFICATION (Turn 128) ==="
echo ""

echo "TARGET 1: Streaming Types"
[ -f "/app/pkg/streaming/stream_types.go" ] && echo "  ✓ COMPLETE" || echo "  ✗ INCOMPLETE"

echo ""
echo "TARGET 2: Endpoint Architecture"
[ -d "/app/pkg/endpoint/cep" ] && [ -d "/app/pkg/endpoint/sep" ] && [ -f "/app/pkg/endpoint/deprecated.go" ] && echo "  ✓ COMPLETE" || echo "  ✗ INCOMPLETE"

echo ""
echo "TARGET 3: Transport Protocol"
grep -q "TTHeaderStreaming.*64" /app/transport/keys.go && grep -q "GRPCStreaming.*128" /app/transport/keys.go && echo "  ✓ Constants COMPLETE" || echo "  ✗ Constants INCOMPLETE"
echo "  Default protocol change: Checking..."
# The spec requires default to be Framed, not PurePayload
# Need to check where default protocol is set

echo ""
echo "TARGET 4: Thrift Codec Fallback"
grep -q "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go && echo "  ✗ Basic exclusion PRESENT" || echo "  ✓ COMPLETE (Basic exclusion removed)"

echo ""
echo "TARGET 5: Client Options"
[ -f "/app/client/option_unary.go" ] && [ -f "/app/client/option_ttstream.go" ] && echo "  ✓ Files exist" || echo "  ✗ Files missing"
grep -c "^func With" /app/client/option_stream.go 2>/dev/null | xargs echo "  option_stream.go functions:"
echo "  (Required: 8+ functions)"

echo ""
echo "TARGET 6: gRPC Diagnostics"
grep -q "func.*Dump.*interface" /app/pkg/remote/trans/nphttp2/conn_pool.go && echo "  ✓ Dump() exists" || echo "  ✗ Dump() missing"
echo "  frame_reader check:"
grep -n "func.*readAndCheckFrameHeader\|func.*readFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go 2>/dev/null | head -3
