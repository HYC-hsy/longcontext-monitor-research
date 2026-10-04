
# Verify Target 4 fix is correct
echo "=== Target 4: thrift_data.go fallback logic ==="
grep -n "CodecType.*Basic" /app/pkg/remote/codec/thrift/thrift_data.go | head -5

# Verify Target 6 frame_reader.go
echo -e "\n=== Target 6: readAndCheckFrameHeader method ==="
grep -n "func.*readAndCheckFrameHeader\|func.*readFrameHeader" /app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go

# Check if Dump() exists on connPool
echo -e "\n=== Target 6: Dump() method on connPool ==="
grep -n "func.*Dump" /app/pkg/remote/trans/nphttp2/conn_pool.go | head -3
