
# Final comprehensive build check
echo "=== FINAL BUILD VERIFICATION ==="
cd /app && go build ./pkg/streaming/... 2>&1 && echo "✓ pkg/streaming"
cd /app && go build ./pkg/endpoint/... 2>&1 && echo "✓ pkg/endpoint"
cd /app && go build ./pkg/remote/codec/thrift/... 2>&1 && echo "✓ pkg/remote/codec/thrift"
cd /app && go build ./pkg/remote/trans/nphttp2/... 2>&1 && echo "✓ pkg/remote/trans/nphttp2"
cd /app && go build ./transport/... 2>&1 && echo "✓ transport"
cd /app && go build ./internal/client/... 2>&1 && echo "✓ internal/client"
cd /app && go build ./client/... 2>&1 && echo "✓ client"
