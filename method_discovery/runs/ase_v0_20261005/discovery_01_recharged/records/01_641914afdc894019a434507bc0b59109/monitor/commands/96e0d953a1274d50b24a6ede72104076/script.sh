
# Check build status
echo "=== BUILD STATUS CHECK ==="
cd /app && go build ./client/... 2>&1 | head -20
