
# Check if frame_reader.go exists
find /app/pkg/remote/trans/nphttp2 -name "*frame*.go" -o -name "*grpc*.go" | grep -E "(frame|grpc)" | head -20
