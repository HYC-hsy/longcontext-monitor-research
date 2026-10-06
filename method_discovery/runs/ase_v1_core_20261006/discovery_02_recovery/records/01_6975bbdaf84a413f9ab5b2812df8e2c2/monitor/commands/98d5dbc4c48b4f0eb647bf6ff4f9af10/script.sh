
# Check if Target 4 Basic codec fallback was finally fixed
echo "=== TARGET 4 FINAL CHECK ==="
grep -c "c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go
echo "Count above (should be 0 if fixed)"
echo ""
echo "Checking the actual fallback logic:"
sed -n '125,145p' /app/pkg/remote/codec/thrift/thrift_data.go
