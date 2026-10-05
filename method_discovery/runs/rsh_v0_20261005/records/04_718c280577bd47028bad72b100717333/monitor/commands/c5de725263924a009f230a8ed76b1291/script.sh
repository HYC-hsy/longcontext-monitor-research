
# Check for the ErrFrameTooLarge error handling in frame_reader.go
cd /app && grep -A 10 "maxReadSize" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | grep -A 8 "fh.Length"
