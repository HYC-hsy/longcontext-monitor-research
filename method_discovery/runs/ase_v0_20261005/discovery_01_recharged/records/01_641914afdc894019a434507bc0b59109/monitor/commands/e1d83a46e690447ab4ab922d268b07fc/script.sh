
# Critical verification: thrift_data.go still has the "if c.CodecType != Basic" guard
# This means Target 4 is NOT complete - Basic codec is still excluded from fallback
echo "=== CRITICAL: Target 4 Issue ==="
echo "thrift_data.go line 66 still has: if c.CodecType != Basic"
echo "This prevents Basic codec from using fallback!"
echo ""
echo "Current code (lines 55-78):"
sed -n '55,78p' /app/pkg/remote/codec/thrift/thrift_data.go
