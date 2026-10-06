
# Run the actual thrift codec tests
echo "=== RUNNING THRIFT CODEC TESTS ==="
cd /app && go test -v ./pkg/remote/codec/thrift/... -run "TestBasic" 2>&1 | head -40
