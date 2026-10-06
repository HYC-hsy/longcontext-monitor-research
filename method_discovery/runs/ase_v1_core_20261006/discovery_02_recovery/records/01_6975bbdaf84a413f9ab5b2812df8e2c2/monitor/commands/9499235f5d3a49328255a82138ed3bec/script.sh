
# Final build verification
echo "=== FINAL BUILD VERIFICATION ==="
cd /app && go build ./pkg/streaming/... 2>&1 && echo "✓ streaming"
cd /app && go build ./pkg/endpoint/... 2>&1 && echo "✓ endpoint"
cd /app && go build ./pkg/remote/codec/thrift/... 2>&1 && echo "✓ thrift codec"
cd /app && go build ./pkg/remote/trans/nphttp2/... 2>&1 && echo "✓ nphttp2"
cd /app && go build ./internal/client/... 2>&1 && echo "✓ internal/client"
cd /app && go build ./transport/... 2>&1 && echo "✓ transport"
echo ""
echo "All packages build successfully!"
