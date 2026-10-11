
# Verify the current build status
cd /app && go build ./... 2>&1
echo ""
echo "Build exit code: $?"
