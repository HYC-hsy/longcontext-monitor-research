
# Comprehensive verification of all 6 targets
echo "=== COMPREHENSIVE TARGET VERIFICATION (Turn 77) ==="
echo ""

# Target 1: Streaming Types
echo "Target 1: Streaming Types and Generic Interfaces"
if [ -f "/app/pkg/streaming/stream_types.go" ]; then
  echo "  ✓ stream_types.go exists"
  grep -c "type.*Streaming.*\[" /app/pkg/streaming/stream_types.go | xargs echo "    Generic types count:"
else
  echo "  ✗ stream_types.go MISSING"
fi

# Target 2: Endpoint Architecture
echo ""
echo "Target 2: Endpoint Architecture"
[ -d "/app/pkg/endpoint/cep" ] && echo "  ✓ cep package exists" || echo "  ✗ cep MISSING"
[ -d "/app/pkg/endpoint/sep" ] && echo "  ✓ sep package exists" || echo "  ✗ sep MISSING"
[ -f "/app/pkg/endpoint/deprecated.go" ] && echo "  ✓ deprecated.go exists" || echo "  ✗ deprecated.go MISSING"
grep -c "DummyDummyMiddleware" /app/pkg/endpoint/cep/endpoint.go 2>/dev/null | xargs echo "    DummyDummyMiddleware:"

# Target 3: Transport Protocol
echo ""
echo "Target 3: Transport Protocol"
grep "TTHeaderStreaming.*64" /app/transport/keys.go >/dev/null && echo "  ✓ TTHeaderStreaming = 64" || echo "  ✗ TTHeaderStreaming wrong"
grep "GRPCStreaming.*128" /app/transport/keys.go >/dev/null && echo "  ✓ GRPCStreaming = 128" || echo "  ✗ GRPCStreaming wrong"

# Target 4: Thrift Codec
echo ""
echo "Target 4: Thrift Codec Fallback"
grep "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go >/dev/null && echo "  ✗ Basic exclusion STILL PRESENT" || echo "  ✓ Basic exclusion removed"

# Target 5: Client Options
echo ""
echo "Target 5: Client Options"
[ -f "/app/client/option_unary.go" ] && echo "  ✓ option_unary.go exists" || echo "  ✗ option_unary.go MISSING"
[ -f "/app/client/option_stream.go" ] && echo "  ✓ option_stream.go exists" || echo "  ✗ option_stream.go MISSING"
[ -f "/app/client/option_ttstream.go" ] && echo "  ✓ option_ttstream.go exists" || echo "  ✗ option_ttstream.go MISSING"

# Target 6: gRPC Diagnostics
echo ""
echo "Target 6: gRPC Diagnostics"
grep -c "func.*Dump.*interface" /app/pkg/remote/trans/nphttp2/conn_pool.go 2>/dev/null | xargs echo "  Dump() method:"
grep "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go >/dev/null && echo "  ✓ readAndCheckFrameHeader exists" || echo "  ✗ readAndCheckFrameHeader MISSING"
