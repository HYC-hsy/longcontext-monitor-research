
# Check current build status
cd /app && go build ./client/... 2>&1 | head -15
