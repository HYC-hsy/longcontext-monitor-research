
# Verify Target 2 corrections and check Target 5/6 progress
cd /app

echo "=== TARGET 2: Verify corrected signatures ==="
echo "cep StreamRecvEndpoint:"
grep "type StreamRecvEndpoint func" pkg/endpoint/cep/endpoint.go

echo ""
echo "cep StreamSendEndpoint:"
grep "type StreamSendEndpoint func" pkg/endpoint/cep/endpoint.go

echo ""
echo "cep StreamEndpoint:"
grep "type StreamEndpoint func" pkg/endpoint/cep/endpoint.go

echo ""
echo "sep StreamRecvEndpoint:"
grep "type StreamRecvEndpoint func" pkg/endpoint/sep/endpoint.go

echo ""
echo "sep StreamEndpoint:"
grep "type StreamEndpoint func" pkg/endpoint/sep/endpoint.go

echo ""
echo "=== TARGET 5: Check implementation completeness ==="
echo "Created files:"
ls -la client/option_unary.go client/option_stream.go client/option_ttstream.go 2>/dev/null && echo "✓ All three files exist" || echo "✗ Missing files"

echo ""
echo "TailOption in option.go:"
grep -n "func TailOption" client/option.go || echo "✗ Not yet added"

echo ""
echo "callopt/streamcall directory:"
ls -la client/callopt/streamcall/ 2>/dev/null && echo "✓ Exists" || echo "✗ Not yet created"

echo ""
echo "=== TARGET 6: Check readAndCheckFrameHeader ==="
grep -n "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go || echo "✗ Still not implemented"
