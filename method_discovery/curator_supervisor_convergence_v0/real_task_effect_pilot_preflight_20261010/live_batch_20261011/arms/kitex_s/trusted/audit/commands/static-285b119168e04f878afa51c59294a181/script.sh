
# Check if the enhanced error format with first4Bytes/second4Bytes exists anywhere
grep -n "first4Bytes\|second4Bytes" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go || echo "NOT FOUND - Required error format is missing"
