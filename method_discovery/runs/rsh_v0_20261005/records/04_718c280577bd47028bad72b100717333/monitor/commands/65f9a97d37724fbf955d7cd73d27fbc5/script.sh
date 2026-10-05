
# Comprehensive verification of all 6 targets

echo "=== TARGET 1: Streaming Types and Generic Interfaces ==="
echo "1. Check Header/Trailer types:"
grep -E "type (Header|Trailer)" /app/pkg/streaming/types.go | head -2

echo -e "\n2. Check ClientStream interface methods:"
grep -A 10 "type ClientStream interface" /app/pkg/streaming/types.go | grep -E "(SendMsg|RecvMsg|Header|Trailer|CloseSend|Context)"

echo -e "\n3. Check ServerStream interface methods:"
grep -A 8 "type ServerStream interface" /app/pkg/streaming/types.go | grep -E "(SendMsg|RecvMsg|SetHeader|SendHeader|SetTrailer)"

echo -e "\n4. Check generic wrapper factories exist:"
grep -E "func New(ServerStreaming|ClientStreaming|BidiStreaming)(Client|Server)" /app/pkg/streaming/generic_*.go

echo -e "\n5. Check Args/Result extensions:"
grep -A 3 "type Args struct" /app/pkg/streaming/streaming.go
grep -A 3 "type Result struct" /app/pkg/streaming/streaming.go

echo -e "\n=== TARGET 2: Endpoint Architecture ==="
echo "6. Check cep.StreamEndpoint signature (returns ClientStream):"
grep "type StreamEndpoint" /app/pkg/endpoint/cep/endpoint.go

echo -e "\n7. Check sep.StreamEndpoint signature (takes ServerStream param):"
grep "type StreamEndpoint" /app/pkg/endpoint/sep/endpoint.go

echo -e "\n8. Check cep EqualsTo methods:"
grep -A 1 "func (e StreamRecvEndpoint) EqualsTo" /app/pkg/endpoint/cep/endpoint.go
grep -A 1 "func (e StreamSendEndpoint) EqualsTo" /app/pkg/endpoint/cep/endpoint.go

echo -e "\n9. Check DummyDummyMiddleware:"
grep "func DummyDummyMiddleware" /app/pkg/endpoint/cep/endpoint.go

echo -e "\n=== TARGET 3: Transport Protocol ==="
echo "10. Check protocol constant values:"
grep -E "(PurePayload|TTHeader|Framed|HTTP|GRPC|HESSIAN2|TTHeaderStreaming|GRPCStreaming)" /app/transport/keys.go | grep -E "Protocol = |= "

echo -e "\n11. Check String() handles composites with Hessian2:"
grep -A 2 "HESSIAN2 != 0" /app/transport/keys.go

echo -e "\n=== TARGET 5: Client Option Category System ==="
echo "12. Check option type aliases in client/option.go:"
grep -E "type (Unary|Stream|TTHeaderStreaming)Option" /app/client/option.go | head -6

echo -e "\n13. Check option files exist:"
ls -1 /app/client/option_{unary,stream,ttstream}.go 2>&1

echo -e "\n14. Check streamcall package:"
ls -1 /app/client/callopt/streamcall/*.go 2>&1 | head -3

echo -e "\n=== TARGET 6: gRPC Diagnostics ==="
echo "15. Check connPool.Dump() method:"
grep -A 1 "func (cp \*connPool) Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go

echo -e "\n16. Check readAndCheckFrameHeader with maxReadSize and hex dump:"
grep -B 1 -A 3 "fh.Length > fr.maxReadSize" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go

echo -e "\n=== BUILD STATUS ==="
echo "17. Verify build success:"
cd /app && go build ./... 2>&1 | grep -E "(error|cannot)" | head -5 || echo "✓ Build successful"
