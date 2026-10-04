
# Check for missing Target 2 and Target 5 files
cd /app
echo "=== Checking Target 2 files ==="
ls -la pkg/endpoint/deprecated.go 2>/dev/null || echo "MISSING: pkg/endpoint/deprecated.go"
grep -c "UnaryEndpoint" pkg/endpoint/endpoint.go || echo "MISSING: UnaryEndpoint in endpoint.go"
grep -c "StreamRecvEndpoint" pkg/endpoint/cep/endpoint.go || echo "MISSING: StreamRecvEndpoint in cep"
grep -c "StreamRecvEndpoint" pkg/endpoint/sep/endpoint.go || echo "MISSING: StreamRecvEndpoint in sep"
echo ""
echo "=== Checking Target 5 files ==="
ls -la client/option_unary.go 2>/dev/null || echo "MISSING: client/option_unary.go"
ls -la client/option_stream.go 2>/dev/null || echo "MISSING: client/option_stream.go"
ls -la client/option_ttstream.go 2>/dev/null || echo "MISSING: client/option_ttstream.go"
ls -la client/callopt/streamcall 2>/dev/null || echo "MISSING: client/callopt/streamcall/"
echo ""
echo "=== Checking Target 6 ==="
grep -n "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go || echo "MISSING: readAndCheckFrameHeader method"
