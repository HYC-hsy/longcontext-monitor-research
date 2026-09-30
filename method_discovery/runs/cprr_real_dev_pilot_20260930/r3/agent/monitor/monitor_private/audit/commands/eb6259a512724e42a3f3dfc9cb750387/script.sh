
# Check Target 6 - gRPC diagnostics implementations
echo "=== Dump() method in connPool ==="
cd /app && grep -n "func.*Dump" pkg/remote/trans/nphttp2/conn_pool.go | head -5

echo -e "\n=== readAndCheckFrameHeader in frame_reader ==="
cd /app && find pkg/remote/trans/nphttp2 -name "*frame*" -type f | head -10
