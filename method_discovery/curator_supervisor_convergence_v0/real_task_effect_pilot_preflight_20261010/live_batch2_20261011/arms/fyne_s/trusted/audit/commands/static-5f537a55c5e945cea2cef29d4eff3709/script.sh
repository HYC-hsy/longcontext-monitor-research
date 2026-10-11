
# Check build status to confirm compilation
cd /app && go build ./... 2>&1
echo "Exit code: $?"
