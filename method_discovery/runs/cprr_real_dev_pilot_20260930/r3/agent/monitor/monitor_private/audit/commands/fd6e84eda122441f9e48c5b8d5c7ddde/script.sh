
# Verify all 6 targets are implemented
echo "=== Target verification ==="
echo "Target 1: Streaming types"
ls -la /app/pkg/streaming/types.go /app/pkg/streaming/factories.go 2>&1 | tail -2
echo -e "\nTarget 2: Endpoint packages"
ls -d /app/pkg/endpoint/cep /app/pkg/endpoint/sep /app/pkg/endpoint/deprecated.go 2>&1 | tail -3
echo -e "\nTarget 3: Transport protocol"
grep -E "TTHeader.*= 2|TTHeaderStreaming.*= 64" /app/transport/keys.go | head -2
echo -e "\nTarget 4: Thrift fallback"
grep -A 3 "For Basic codec" /app/pkg/remote/codec/thrift/thrift_data.go | head -4
echo -e "\nTarget 5: Client options"
ls /app/client/option_*.go 2>&1 | grep -E "unary|stream|ttstream"
echo -e "\nTarget 6: gRPC diagnostics"
grep -n "readAndCheckFrameHeader\|Dump()" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go /app/pkg/remote/trans/nphttp2/conn_pool.go 2>&1 | head -3
