
# Verify build actually succeeded - check for any errors
cd /app && go build ./... 2>&1 | grep -i "error" | head -10
echo "Build exit code check:"
cd /app && go build ./... >/dev/null 2>&1 && echo "BUILD SUCCESS" || echo "BUILD FAILED"
