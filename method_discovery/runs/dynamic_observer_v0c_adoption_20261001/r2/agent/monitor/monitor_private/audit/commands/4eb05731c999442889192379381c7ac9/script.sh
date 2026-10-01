
# Check Target 4: Thrift codec fallback implementation
echo "=== Target 4: Thrift Codec Fallback ==="
echo "Checking unmarshalThriftData:"
grep -A 15 "func unmarshalThriftData" /app/pkg/remote/codec/thrift/thrift_data.go | grep -A 10 "c.CodecType == Basic"
echo ""
echo "Checking marshalThriftData:"
grep -A 15 "func marshalThriftData" /app/pkg/remote/codec/thrift/thrift_data.go | grep -A 10 "c.CodecType == Basic"
