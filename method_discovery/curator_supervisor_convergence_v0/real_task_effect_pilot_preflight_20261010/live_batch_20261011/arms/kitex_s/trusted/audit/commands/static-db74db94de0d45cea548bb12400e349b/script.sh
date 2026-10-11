
# Check for the enhanced error message with hex dump
grep -A3 "invalid frame" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -10
