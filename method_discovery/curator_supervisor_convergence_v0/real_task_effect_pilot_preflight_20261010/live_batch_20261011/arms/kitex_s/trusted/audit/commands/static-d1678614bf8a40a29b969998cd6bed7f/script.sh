cd /app

echo "=== TARGET 4: Verifying Thrift Codec Fallback for Basic ==="
echo "Checking MarshalThriftData implementation..."
grep -n "func MarshalThriftData" pkg/remote/codec/thrift/thrift.go
echo ""
echo "Looking for Basic codec handling in marshal..."
sed -n '130,180p' pkg/remote/codec/thrift/thrift.go | grep -n "Basic\|case\|FastWrite\|Frugal" | head -20
