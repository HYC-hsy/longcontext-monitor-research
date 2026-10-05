
# Check the Unmarshal method to see if it also has the Basic codec blocking issue
grep -A 30 "func (c thriftCodec) Unmarshal" /app/pkg/remote/codec/thrift/thrift.go | grep -A 15 "if c.CodecType"
