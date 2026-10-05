
# Verify Target 4 fix: Basic codec exclusion should be REMOVED
echo "=== Verifying Target 4 Fix (thrift_data.go marshalThriftData) ==="
grep -n "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go || echo "✓ Basic codec exclusion REMOVED from marshalThriftData"
