
# Verify thrift_data.go has been updated for Basic codec fallback
echo "=== Checking thrift_data.go for Basic codec fallback ==="
grep -A8 "if c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go || echo "Pattern not found - checking if fallback is now unconditional"
