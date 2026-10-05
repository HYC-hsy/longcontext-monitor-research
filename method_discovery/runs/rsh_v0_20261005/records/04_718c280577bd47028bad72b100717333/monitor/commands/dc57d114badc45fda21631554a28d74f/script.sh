
# Check for the error format with hex dump in frame_reader.go
cd /app && grep -B 5 -A 5 "first4Bytes\|second4Bytes" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
