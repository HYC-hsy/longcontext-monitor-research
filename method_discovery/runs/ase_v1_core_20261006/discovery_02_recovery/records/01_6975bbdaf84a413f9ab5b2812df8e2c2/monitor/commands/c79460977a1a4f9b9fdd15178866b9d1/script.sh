
# Build verification
echo "=== BUILD VERIFICATION ==="
cd /app && go build ./pkg/endpoint/... 2>&1 && echo "✓ pkg/endpoint builds"
cd /app && go build ./pkg/remote/codec/thrift/... 2>&1 && echo "✓ pkg/remote/codec/thrift builds"
cd /app && go build ./pkg/remote/trans/nphttp2/... 2>&1 && echo "✓ pkg/remote/trans/nphttp2 builds"
cd /app && go build ./pkg/streaming/... 2>&1 && echo "✓ pkg/streaming builds"
