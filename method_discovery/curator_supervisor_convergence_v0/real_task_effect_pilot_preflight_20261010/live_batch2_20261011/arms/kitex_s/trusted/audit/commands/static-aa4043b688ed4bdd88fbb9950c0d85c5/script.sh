
# Build and verify no errors
cd /app && go build ./... 2>&1
echo ""
echo "=== BUILD STATUS: $? ==="
