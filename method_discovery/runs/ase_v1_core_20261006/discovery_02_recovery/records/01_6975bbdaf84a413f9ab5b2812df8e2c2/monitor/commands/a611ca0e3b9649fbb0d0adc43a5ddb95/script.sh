
# Check the build error details
cd /app && go build ./client/... 2>&1 | head -30
