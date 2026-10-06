
# Check if the client/stream.go issue was resolved
echo "=== CLIENT BUILD STATUS ==="
cd /app && go build ./client/... 2>&1 | head -15
