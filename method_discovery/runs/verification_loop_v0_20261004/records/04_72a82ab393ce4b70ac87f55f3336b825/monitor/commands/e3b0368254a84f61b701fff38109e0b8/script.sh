
# Comprehensive verification of all 6 targets
cd /app

echo "=== TARGET 2: Endpoint Architecture - Checking Required Types ==="
echo ""
echo "cep package types:"
grep -E "^type|^func" pkg/endpoint/cep/endpoint.go | head -20

echo ""
echo "sep package types:"
grep -E "^type|^func" pkg/endpoint/sep/endpoint.go | head -20

echo ""
echo "Base endpoint package - UnaryEndpoint types:"
grep -E "type Unary|func.*Unary" pkg/endpoint/endpoint.go || echo "MISSING: UnaryEndpoint types"

echo ""
echo "deprecated.go:"
ls -la pkg/endpoint/deprecated.go 2>/dev/null || echo "MISSING: pkg/endpoint/deprecated.go"

echo ""
echo "=== TARGET 5: Client Options - Checking Required Files ==="
ls -la client/option_unary.go 2>/dev/null || echo "MISSING: client/option_unary.go"
ls -la client/option_stream.go 2>/dev/null || echo "MISSING: client/option_stream.go"  
ls -la client/option_ttstream.go 2>/dev/null || echo "MISSING: client/option_ttstream.go"
ls -la client/callopt/streamcall 2>/dev/null || echo "MISSING: client/callopt/streamcall directory"

echo ""
echo "=== TARGET 6: gRPC Diagnostics - Checking readAndCheckFrameHeader ==="
grep -n "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go || echo "MISSING: readAndCheckFrameHeader method"
grep -n "func readFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "ISSUE: standalone readFrameHeader still exists (should be replaced)"
