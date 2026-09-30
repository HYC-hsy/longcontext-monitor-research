
# Check status of all three corrections
echo "=== Target 4: Check thrift fallback ==="
cd /app && git diff pkg/remote/codec/thrift/thrift_data.go | grep -A 10 "Basic codec" | head -20

echo -e "\n=== Target 5: Check option files ==="
ls -la /app/client/option_*.go | awk '{print $9}'

echo -e "\n=== Target 6: Check frame reader ==="
cd /app && grep -n "readAndCheckFrameHeader" pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -3
