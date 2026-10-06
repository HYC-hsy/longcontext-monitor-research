
# Comprehensive final verification of all 6 targets
echo "=== FINAL VERIFICATION OF ALL 6 TARGETS ==="
echo ""
echo "TARGET 1: Streaming Types"
echo "- 6 generic types exist:"
grep -c "^type.*StreamingClient\[" /app/pkg/streaming/streaming.go
grep -c "^type.*StreamingServer\[" /app/pkg/streaming/streaming.go
echo "- Args/Result extended:"
grep "ClientStream\|ServerStream" /app/pkg/streaming/streaming.go | grep -E "^[[:space:]]+(ClientStream|ServerStream)" | head -4
echo ""
echo "TARGET 2: Endpoint Architecture"
echo "- CEP StreamEndpoint returns ClientStream:"
grep "type.*StreamEndpoint.*func" /app/pkg/endpoint/cep/endpoint.go | head -1
echo "- StreamRecvEndpoint signature:"
grep "type StreamRecvEndpoint" /app/pkg/endpoint/cep/endpoint.go
echo "- DummyDummyMiddleware exists:"
grep -c "func DummyDummy" /app/pkg/endpoint/cep/endpoint.go
echo "- UnaryChain exists:"
grep -c "func UnaryChain" /app/pkg/endpoint/endpoint.go
echo ""
echo "TARGET 3: Transport Protocol"
echo "- TTHeaderStreaming value:"
grep "TTHeaderStreaming.*=" /app/transport/keys.go | grep -v "const"
echo "- GRPCStreaming value:"
grep "GRPCStreaming.*=" /app/transport/keys.go | grep -v "const"
echo ""
echo "TARGET 4: Thrift Codec Fallback"
echo "- Basic codec exclusion removed (should show 0 or 1):"
grep -c "c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go
echo ""
echo "TARGET 6: gRPC Diagnostics"
echo "- conn_pool Dump() return type:"
grep "func.*Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go | head -1
echo "- readAndCheckFrameHeader exists:"
grep -c "func readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
