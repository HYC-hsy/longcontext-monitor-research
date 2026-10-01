
# Verify Target 4: Basic codec fallback
# Check if fallback logic allows Basic codec (should NOT have "c.CodecType != Basic" restriction)
grep -B 2 -A 5 "fallback" /app/pkg/remote/codec/thrift/thrift_data.go | grep -E "(CodecType|Basic|FastCodec|Frugal)" | head -10
