
# Check the frame_reader.go for the new method signature
cd /app && grep -A 15 "func (fr \*Framer) readAndCheckFrameHeader()" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
