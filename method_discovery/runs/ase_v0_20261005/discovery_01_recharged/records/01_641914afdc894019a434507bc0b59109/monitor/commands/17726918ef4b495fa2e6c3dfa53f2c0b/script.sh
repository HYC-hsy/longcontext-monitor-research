
# Check current build status
echo "=== BUILD STATUS CHECK (Turn 175) ==="
echo ""
cd /app && go build ./client/... 2>&1 | head -20
