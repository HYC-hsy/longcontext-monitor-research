
# Check what the test actually expects
echo "=== TEST EXPECTATIONS ==="
grep -B5 -A15 "BasicCodec" /app/pkg/remote/codec/thrift/thrift_data_test.go | head -30
