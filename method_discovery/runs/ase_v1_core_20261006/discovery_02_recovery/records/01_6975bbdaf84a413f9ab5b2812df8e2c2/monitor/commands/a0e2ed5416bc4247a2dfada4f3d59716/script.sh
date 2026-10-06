
# Check Issue 2 more carefully - the agent claims it's fixed
echo "=== ISSUE 2 DETAILED CHECK ==="
echo "Looking for Basic codec fallback in marshalThriftData:"
grep -B3 -A12 "c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go | head -18
echo ""
echo "Also check unmarshalThriftData:"
grep -B3 -A12 "c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go | tail -18
