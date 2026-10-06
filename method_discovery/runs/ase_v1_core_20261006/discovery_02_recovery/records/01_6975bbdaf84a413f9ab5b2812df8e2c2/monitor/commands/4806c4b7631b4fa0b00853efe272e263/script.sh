
# Check if all tests pass now
echo "=== RUNNING ALL THRIFT CODEC TESTS ==="
cd /app && go test ./pkg/remote/codec/thrift/... -v 2>&1 | tail -30
