cd /app

echo "=== Finding transport protocol file ==="
find . -name "*.go" -path "*/transport*" | grep -E "(transport\.go|protocol\.go)" | grep -v test | grep -v vendor | head -10

echo ""
echo "=== TARGET 6: Verifying Dump method ==="
grep -n "func.*\*connPool.*Dump" pkg/remote/trans/nphttp2/conn_pool.go

echo ""
echo "=== Checking frame_reader for readAndCheckFrameHeader ==="
grep -n "func.*readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go
