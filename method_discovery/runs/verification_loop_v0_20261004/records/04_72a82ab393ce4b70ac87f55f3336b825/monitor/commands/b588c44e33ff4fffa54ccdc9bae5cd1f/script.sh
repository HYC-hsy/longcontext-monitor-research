
# Check for readFrameHeader function in frame_reader.go
cd /app
grep -n "func readFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
grep -n "func (fr \*Framer) readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
