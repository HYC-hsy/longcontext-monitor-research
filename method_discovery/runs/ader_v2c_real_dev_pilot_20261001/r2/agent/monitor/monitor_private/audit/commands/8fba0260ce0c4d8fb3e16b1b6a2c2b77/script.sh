
# Verify readAndCheckFrameHeader exists with enhanced error
grep -A 15 "func (fr \*Framer) readAndCheckFrameHeader()" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -20
