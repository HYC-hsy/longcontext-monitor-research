
# Verify Target 1: Check ClientStream/ServerStream interfaces exist
grep -A 2 "type ClientStream interface" /app/pkg/streaming/types.go
grep -A 2 "type ServerStream interface" /app/pkg/streaming/types.go

# Verify Target 2: Check cep and sep packages have correct StreamEndpoint signatures
grep "type StreamEndpoint" /app/pkg/endpoint/cep/endpoint.go
grep "type StreamEndpoint" /app/pkg/endpoint/sep/endpoint.go

# Verify Target 3: Check protocol constant values
grep -E "TTHeaderStreaming|GRPCStreaming" /app/transport/keys.go | head -3

# Verify Target 6: Check readAndCheckFrameHeader method and maxReadSize check
grep -A 5 "func (fr \*Framer) readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -6
grep -B 2 -A 2 "fh.Length > fr.maxReadSize" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
