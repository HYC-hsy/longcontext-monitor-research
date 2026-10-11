
# Verify Target 6 - Dump() method and frame reader enhancement
echo "=== Target 6: Dump() method ===" 
grep -n "func.*Dump()" /app/pkg/remote/trans/nphttp2/conn_pool.go
echo "---"
echo "=== Target 6: readAndCheckFrameHeader method ==="
grep -n "readAndCheckFrameHeader\|first4Bytes.*second4Bytes" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go | head -5
