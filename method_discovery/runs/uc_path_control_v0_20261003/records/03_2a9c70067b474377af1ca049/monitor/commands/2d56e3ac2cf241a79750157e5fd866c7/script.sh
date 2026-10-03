echo "Verifying all critical requirements:"
echo "1. WithStreamMiddleware:" && grep -n "WithStreamMiddleware" /app/client/option_stream.go | head -1
echo "2. TailOption:" && grep -n "func TailOption" /app/client/option.go | head -1
echo "3. streamcall WithRecvTimeout:" && grep -n "func WithRecvTimeout" /app/client/callopt/streamcall/streamcall.go | head -1
echo "4. Hex dump error:" && grep -n "first4Bytes.*second4Bytes" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -1
echo "5. readAndCheckFrameHeader:" && grep -n "func readAndCheckFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -1