
# Check the exact error format when maxReadSize is exceeded
grep -B5 -A5 "maxReadSize" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -A10 "if fh.Length"
