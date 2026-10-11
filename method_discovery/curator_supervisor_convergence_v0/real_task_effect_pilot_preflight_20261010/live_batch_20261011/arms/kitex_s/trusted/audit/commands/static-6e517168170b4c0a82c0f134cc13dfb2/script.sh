
# Check Target 4: Thrift codec fallback
echo "=== Checking Target 4: Thrift Codec Fallback ==="
ls -la /app/pkg/remote/codec/thrift/*.go | grep -E "thrift_data|codec"
echo ""
grep -n "MarshalThriftData\|UnmarshalThriftData" /app/pkg/remote/codec/thrift/thrift_data.go 2>/dev/null | head -20
