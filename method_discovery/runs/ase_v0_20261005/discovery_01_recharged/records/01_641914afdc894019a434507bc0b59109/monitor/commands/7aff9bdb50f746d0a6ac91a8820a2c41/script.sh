
# Check build status
echo "=== BUILD STATUS ==="
cd /app && go build ./client/... 2>&1 | head -15
