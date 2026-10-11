
# Check if Basic codec fallback is actually implemented (should NOT exclude Basic anymore)
grep -n "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go || echo "Pattern not found - may have been fixed"
echo "---"
# Check the actual fallback logic
grep -A 15 "if typecodec.Apache" /app/pkg/remote/codec/thrift/thrift_data.go | head -20
