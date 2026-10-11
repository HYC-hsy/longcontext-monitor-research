
# Check Target 6 requirement 2 - Frame reader hex dump enhancement
echo "=== Target 6 Req 2: readAndCheckFrameHeader with hex dump ==="
grep -A 10 "readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -20
echo "---"
grep "first4Bytes.*second4Bytes\|ErrFrameTooLarge.*invalid frame" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
