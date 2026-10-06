
# Check builds
echo "=== BUILD VERIFICATION ==="
cd /app && go build ./pkg/streaming/... 2>&1 | head -10
