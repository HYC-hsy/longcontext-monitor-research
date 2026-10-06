
# Check if builds pass
echo "=== BUILD VERIFICATION ==="
cd /app && go build ./pkg/endpoint/... 2>&1 && echo "✓ endpoint builds"
cd /app && go build ./pkg/remote/codec/thrift/... 2>&1 && echo "✓ thrift codec builds"
cd /app && go build ./pkg/remote/trans/nphttp2/... 2>&1 | head -5
