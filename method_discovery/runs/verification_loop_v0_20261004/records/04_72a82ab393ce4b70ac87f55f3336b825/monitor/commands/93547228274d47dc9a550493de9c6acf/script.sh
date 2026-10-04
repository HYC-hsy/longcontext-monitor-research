
# Comprehensive final verification of all 6 targets
cd /app

echo "=== BUILD STATUS ==="
go build ./... 2>&1 | tee /tmp/build_output.txt | head -40

echo ""
echo "=== TARGET 1: Streaming Types - Verification ==="
grep -c "type ClientStream interface" pkg/streaming/types.go && echo "✓ ClientStream"
grep -c "type ServerStream interface" pkg/streaming/types.go && echo "✓ ServerStream"
grep -c "ClientStream ClientStream" pkg/streaming/streaming.go && echo "✓ Args/Result extended"
grep -c "type.*StreamingClient\[" pkg/streaming/generic_streams.go && echo "✓ Generic types"

echo ""
echo "=== TARGET 2: Endpoint Architecture - Verification ==="
test -f pkg/endpoint/deprecated.go && echo "✓ deprecated.go exists"
test -f pkg/endpoint/cep/endpoint.go && echo "✓ cep package exists"
test -f pkg/endpoint/sep/endpoint.go && echo "✓ sep package exists"
grep -c "DummyDummyMiddleware" pkg/endpoint/cep/endpoint.go && echo "✓ DummyDummyMiddleware"
grep -c "type UnaryEndpoint " pkg/endpoint/endpoint.go && echo "✓ UnaryEndpoint"
grep -c "EqualsTo.*StreamRecvEndpoint" pkg/endpoint/cep/endpoint.go && echo "✓ EqualsTo methods"

echo ""
echo "=== TARGET 3: Transport Protocol - Verification ==="
grep "TTHeaderStreaming Protocol = 64" transport/keys.go && echo "✓ TTHeaderStreaming=64"
grep "GRPCStreaming Protocol = 128" transport/keys.go && echo "✓ GRPCStreaming=128"
grep -c "strings.Join(parts" transport/keys.go && echo "✓ Composite String() logic"

echo ""
echo "=== TARGET 4: Thrift Codec - Verification ==="
grep -c "FastCodec\|Frugal" pkg/remote/codec/thrift/thrift_data.go && echo "✓ Fallback logic present"

echo ""
echo "=== TARGET 5: Client Options - Verification ==="
test -f client/option_unary.go && echo "✓ option_unary.go"
test -f client/option_stream.go && echo "✓ option_stream.go"
test -f client/option_ttstream.go && echo "✓ option_ttstream.go"
grep -c "func TailOption" client/option.go && echo "✓ TailOption"
test -f client/callopt/streamcall/streamcall.go && echo "✓ streamcall package"

echo ""
echo "=== TARGET 6: gRPC Diagnostics - Verification ==="
grep -c "func (p \*connPool) Dump()" pkg/remote/trans/nphttp2/conn_pool.go && echo "✓ Dump()"
grep -c "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go && echo "✓ readAndCheckFrameHeader"

echo ""
echo "=== Build Error Count ==="
wc -l < /tmp/build_output.txt
