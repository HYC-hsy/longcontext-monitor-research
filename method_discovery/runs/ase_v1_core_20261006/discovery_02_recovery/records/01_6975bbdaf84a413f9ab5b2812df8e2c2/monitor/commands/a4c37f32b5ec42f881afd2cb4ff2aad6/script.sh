
# Check Target 4 more carefully - look at the actual fallback implementation
echo "=== TARGET 4 DETAILED CHECK ==="
echo "Checking if Basic codec gets fallback in marshalThriftData:"
grep -B5 -A15 "func.*marshalThriftData" /app/pkg/remote/codec/thrift/thrift_data.go | head -25
