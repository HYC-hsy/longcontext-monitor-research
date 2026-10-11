cd /app

echo "=== TARGET 3: Transport Protocol Constants ==="
echo "Checking protocol constant values..."
grep -n "const\|TTHeaderStreaming\|GRPCStreaming\|TTHeaderFramed" pkg/protocol/transport/transport.go | grep -A2 -B2 "TTHeaderStreaming\|GRPCStreaming" | head -20

echo ""
echo "=== TARGET 4: Thrift Codec Fallback ==="
echo "Checking MarshalThriftData for Basic codec fallback..."
grep -n "func MarshalThriftData\|case Basic\|FastWrite\|BLength" pkg/remote/codec/thrift/thrift.go | head -15

echo ""
echo "=== TARGET 5: Client Options Structure ==="
ls -la client/option*.go 2>/dev/null | grep -v ".go~"

echo ""
echo "Checking WithUnaryOptions and WithStreamOptions..."
grep -n "func WithUnaryOptions\|func WithStreamOptions\|func WithTTHeaderStreamingOptions" client/option*.go | head -10

echo ""
echo "=== TARGET 6: Connection Pool Dump ==="
grep -n "func.*Dump.*interface" pkg/remote/trans/nphttp2/conn_pool.go | head -5
