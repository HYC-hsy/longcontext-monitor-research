
# Verify all 6 targets final status
echo "=== ALL 6 TARGETS FINAL VERIFICATION ==="
echo ""
echo "Target 1: Streaming Types"
[ -f "/app/pkg/streaming/stream_types.go" ] && echo "  ✓ COMPLETE" || echo "  ✗ INCOMPLETE"

echo ""
echo "Target 2: Endpoint Architecture"  
[ -d "/app/pkg/endpoint/cep" ] && [ -d "/app/pkg/endpoint/sep" ] && echo "  ✓ COMPLETE" || echo "  ✗ INCOMPLETE"

echo ""
echo "Target 3: Transport Protocol"
grep -q "r.transportProtocol = transport.Framed" /app/pkg/rpcinfo/rpcconfig.go && echo "  ✓ COMPLETE (default→Framed)" || echo "  ✗ INCOMPLETE"

echo ""
echo "Target 4: Thrift Codec Fallback"
grep -q "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go && echo "  ✗ INCOMPLETE" || echo "  ✓ COMPLETE (Basic exclusion removed)"

echo ""
echo "Target 5: Client Options"
[ -f "/app/client/option_unary.go" ] && [ -f "/app/client/option_ttstream.go" ] && echo "  ✓ Files exist" || echo "  ✗ Files missing"
grep -c "^func With" /app/client/option_stream.go | xargs echo "  option_stream.go functions:"
echo "  Required: 8+ functions"

echo ""
echo "Target 6: gRPC Diagnostics"
grep -q "func (fr \*Framer) readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "  ✓ readAndCheckFrameHeader exists" || echo "  ✗ Missing"
grep -q "func.*Dump.*interface" /app/pkg/remote/trans/nphttp2/conn_pool.go && echo "  ✓ Dump() exists" || echo "  ✗ Missing"
