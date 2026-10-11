cd /app

echo "=== Finding actual transport protocol file ==="
find . -type f -name "*.go" | xargs grep -l "const.*TTHeaderStreaming\|const.*GRPCStreaming" | grep -v vendor | grep -v test

echo ""
echo "=== TARGET 4 CRITICAL: Checking Basic codec fallback logic ==="
echo "Full context around Basic codec handling:"
sed -n '130,200p' pkg/remote/codec/thrift/thrift.go | cat -n
