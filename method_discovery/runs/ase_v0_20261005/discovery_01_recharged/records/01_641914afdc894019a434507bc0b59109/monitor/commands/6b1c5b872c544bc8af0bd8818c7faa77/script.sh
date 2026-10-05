
# Check unmarshalThriftData for same issue
echo "=== Checking unmarshalThriftData for Basic exclusion ==="
grep -n -A10 "func (c thriftCodec) unmarshalThriftData" /app/pkg/remote/codec/thrift/thrift_data.go | grep -A10 "CodecType != Basic"
