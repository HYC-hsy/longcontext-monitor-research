
# Check Target 6 frame_reader for readAndCheckFrameHeader
cd /app && grep -n "readAndCheckFrameHeader\|readFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -10
