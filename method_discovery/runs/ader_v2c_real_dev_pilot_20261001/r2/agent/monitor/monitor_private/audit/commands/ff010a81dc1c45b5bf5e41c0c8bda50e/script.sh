
# Get the full error message from readAndCheckFrameHeader
grep -A 25 "if fh.Length > fr.maxReadSize" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -30
