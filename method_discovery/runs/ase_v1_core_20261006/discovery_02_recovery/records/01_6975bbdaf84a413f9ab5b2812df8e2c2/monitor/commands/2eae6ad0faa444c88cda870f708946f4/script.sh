
# Verify against ORIGINAL task specification (my reference.md)
echo "=== VERIFICATION AGAINST ORIGINAL TASK SPEC ==="
echo ""
echo "Target 1: Streaming Types (Header/Trailer as map[string]string)"
grep -c "^type Header map\[string\]string" /app/pkg/streaming/streaming.go
echo ""
echo "Target 2: CEP/SEP endpoint packages"
test -d /app/pkg/endpoint/cep && echo "CEP EXISTS" || echo "CEP MISSING"
test -d /app/pkg/endpoint/sep && echo "SEP EXISTS" || echo "SEP MISSING"
echo ""
echo "Target 3: Transport protocols"
grep -c "TTHeaderStreaming.*64" /app/transport/keys.go
grep -c "GRPCStreaming.*128" /app/transport/keys.go
echo ""
echo "Target 4: Basic codec fallback (no exclusion)"
grep -c "c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go
echo ""
echo "Target 6: gRPC diagnostics"
grep -c "func.*Dump.*interface{}" /app/pkg/remote/trans/nphttp2/conn_pool.go
grep -c "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
