
# Check for readAndCheckFrameHeader method in frame_reader.go
grep -n "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -5

# Check for hex formatting in error (first4Bytes, second4Bytes)
grep -n "first4Bytes.*second4Bytes" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -3

# Check if WithFailureRetry stores in UnaryOptions
grep -A5 "func WithFailureRetry" /app/client/option.go 2>/dev/null | head -10
