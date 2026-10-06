
# Verify Target 4 Basic codec fallback is correct
echo "=== TARGET 4 FINAL VERIFICATION ==="
echo "Checking if Basic codec gets fallback (the one != Basic occurrence):"
grep -B5 -A12 "c.CodecType != Basic" /app/pkg/remote/codec/thrift/thrift_data.go
